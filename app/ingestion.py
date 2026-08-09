from copy import deepcopy
from dataclasses import asdict
from threading import RLock

from app.models import Classification, IngestResult, NormalizedInboundEvent


class VersionConflictError(Exception):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__("version_conflict")
        self.expected_version = expected_version
        self.current_version = current_version


class ConversationNotFoundError(Exception):
    pass


_ASSIGNMENT_RULES = [
    {
        "id": "rule-shipment-delay",
        "priority": 10,
        "conditions": {"request_type": "shipment_delay"},
        "target": {
            "queue_id": "queue-freight-operations",
            "owner_id": "operator-alex",
        },
        "enabled": True,
    },
    {
        "id": "rule-fallback-unassigned",
        "priority": 1000,
        "conditions": {},
        "target": {"queue_id": "queue-unassigned", "owner_id": None},
        "enabled": True,
    },
]


class InMemoryInbox:
    """Small local repository with database-like identity constraints.

    The indexes intentionally mirror the future PostgreSQL uniqueness rules:
    provider event identity and provider message identity are workspace/account
    scoped. The repository is a reversible fixture adapter, not the production
    persistence choice.
    """

    def __init__(self) -> None:
        self._events: dict[tuple[str, str, str], NormalizedInboundEvent] = {}
        self._event_to_conversation: dict[tuple[str, str, str], str] = {}
        self._message_to_conversation: dict[tuple[str, str, str], str] = {}
        self._conversations: dict[str, dict[str, object]] = {}
        self._comment_commands: dict[tuple[str, str, str], dict[str, object]] = {}
        self._lock = RLock()

    def ingest(self, event: NormalizedInboundEvent) -> IngestResult:
        event_key = (
            event.workspace_id,
            event.provider_account_id,
            event.event_id,
        )
        message_key = (
            event.workspace_id,
            event.provider_account_id,
            event.provider_message_id,
        )
        conversation_id = self._conversation_id(event.provider_thread_id)

        with self._lock:
            if event_key in self._event_to_conversation:
                return IngestResult(
                    accepted=False,
                    duplicate=True,
                    conversation_id=self._event_to_conversation[event_key],
                    duplicate_reason="event_id",
                )

            if message_key in self._message_to_conversation:
                return IngestResult(
                    accepted=False,
                    duplicate=True,
                    conversation_id=self._message_to_conversation[message_key],
                    duplicate_reason="provider_message_id",
                )

            self._events[event_key] = event
            self._event_to_conversation[event_key] = conversation_id
            self._message_to_conversation[message_key] = conversation_id
            if conversation_id in self._conversations:
                conversation = self._conversations[conversation_id]
                self._append_message(conversation, event)
                conversation["version"] = int(conversation["version"]) + 1
                self._append_activity(
                    conversation,
                    event_type="message_imported",
                    actor={"type": "system", "id": None},
                    payload={
                        "provider_account_id": event.provider_account_id,
                        "provider_thread_id": event.provider_thread_id,
                        "provider_message_id": event.provider_message_id,
                    },
                )
            else:
                self._conversations[conversation_id] = self._new_conversation(
                    conversation_id,
                    event,
                )
                self._apply_fixture_intelligence(self._conversations[conversation_id])

        return IngestResult(
            accepted=True,
            duplicate=False,
            conversation_id=conversation_id,
        )

    def get_conversation(self, conversation_id: str) -> dict[str, object] | None:
        with self._lock:
            conversation = self._conversations.get(conversation_id)
            return deepcopy(conversation) if conversation is not None else None

    def list_conversations(
        self,
        *,
        workspace_id: str,
        status: str | None = None,
        queue: str | None = None,
        owner: str | None = None,
        priority: str | None = None,
        sla_state: str | None = None,
        channel: str | None = None,
    ) -> list[dict[str, object]]:
        with self._lock:
            conversations = []
            for conversation in self._conversations.values():
                if conversation["workspace_id"] != workspace_id:
                    continue
                if status is not None and conversation["status"] != status:
                    continue
                if queue is not None and conversation["queue_id"] != queue:
                    continue
                if owner is not None and conversation["owner_id"] != owner:
                    continue
                if priority is not None and conversation["priority"] != priority:
                    continue
                if sla_state is not None and conversation["sla_state"] != sla_state:
                    continue
                if channel is not None and conversation["channel"] != channel:
                    continue
                conversations.append(deepcopy(conversation))
            return conversations

    def run_ai(
        self,
        conversation_id: str,
        *,
        action: str,
        workspace_id: str | None = None,
    ) -> dict[str, object]:
        if action not in {"classify", "classify_and_route", "route"}:
            raise ValueError(f"unsupported_ai_action:{action}")

        with self._lock:
            conversation = self._require_conversation(conversation_id, workspace_id)
            classification = conversation.get("classification")
            route_suggestion = None
            changed = False

            if action in {"classify", "classify_and_route"} and classification is None:
                classification = self._classify(conversation)
                conversation["classification"] = classification
                conversation["request_type"] = classification["request_type"]
                conversation["priority"] = classification["priority"]
                conversation["confidence"] = classification["confidence"]
                self._append_activity(
                    conversation,
                    event_type="classified",
                    actor={"type": "ai", "id": "fixture-classifier"},
                    payload=classification,
                )
                changed = True

            if action in {"classify_and_route", "route"}:
                route_suggestion = self._suggest_route(
                    str(classification["request_type"])
                )
                if conversation.get("suggested_queue_id") != route_suggestion["queue_id"]:
                    conversation["suggested_queue_id"] = route_suggestion["queue_id"]
                    conversation["suggested_owner_id"] = route_suggestion["owner_id"]
                    conversation["unassigned_reason"] = (
                        None
                        if route_suggestion["owner_id"] is not None
                        else "No ordered rule supplied an owner."
                    )
                    changed = True

            if changed:
                conversation["version"] = int(conversation["version"]) + 1

            return {
                "job_id": f"job-{action}-{conversation_id}",
                "state": "completed",
                "input_version": int(conversation["version"]) - (1 if changed else 0),
                "version": conversation["version"],
                "classification": classification,
                "route_suggestion": route_suggestion,
            }

    def assign_conversation(
        self,
        conversation_id: str,
        *,
        owner_id: str | None,
        queue_id: str | None,
        expected_version: int,
        actor_id: str,
        workspace_id: str | None = None,
    ) -> dict[str, object]:
        with self._lock:
            conversation = self._require_conversation(conversation_id, workspace_id)
            self._check_version(conversation, expected_version)
            previous = {
                "owner_id": conversation["owner_id"],
                "queue_id": conversation["queue_id"],
            }
            conversation["owner_id"] = owner_id
            conversation["queue_id"] = queue_id
            conversation["assignment"] = {
                "queue_id": queue_id,
                "owner_id": owner_id,
                "source": "operator",
                "rule_id": None,
                "reason": "Assigned by an operator.",
            }
            conversation["unassigned_reason"] = (
                None if owner_id is not None else "Operator has not assigned an owner."
            )
            conversation.setdefault("assignment_history", []).append(
                {
                    "actor_id": actor_id,
                    "previous": previous,
                    "new": {"owner_id": owner_id, "queue_id": queue_id},
                }
            )
            conversation["version"] = int(conversation["version"]) + 1
            self._append_activity(
                conversation,
                event_type="assigned",
                actor={"type": "user", "id": actor_id},
                payload={
                    "previous": previous,
                    "new": {"owner_id": owner_id, "queue_id": queue_id},
                },
            )
            return deepcopy(conversation)

    def claim_conversation(
        self,
        conversation_id: str,
        *,
        actor_id: str,
        expected_version: int,
        workspace_id: str | None = None,
    ) -> dict[str, object]:
        with self._lock:
            conversation = self._require_conversation(conversation_id, workspace_id)
            self._check_version(conversation, expected_version)
            conversation["owner_id"] = actor_id
            conversation["claim_state"] = "claimed"
            conversation["active_viewer_id"] = actor_id
            conversation["active_editor_id"] = actor_id
            conversation["claim"] = {
                "state": "claimed",
                "claimed_by": actor_id,
            }
            conversation["version"] = int(conversation["version"]) + 1
            self._append_activity(
                conversation,
                event_type="claimed",
                actor={"type": "user", "id": actor_id},
                payload={"owner_id": actor_id},
            )
            return deepcopy(conversation)

    def add_comment(
        self,
        conversation_id: str,
        *,
        body: str,
        actor_id: str,
        client_request_id: str,
        expected_version: int,
        workspace_id: str | None = None,
    ) -> dict[str, object]:
        command_key = (workspace_id or "", conversation_id, client_request_id)
        with self._lock:
            if command_key in self._comment_commands:
                return deepcopy(self._comment_commands[command_key])
            conversation = self._require_conversation(conversation_id, workspace_id)
            self._check_version(conversation, expected_version)
            comment = {
                "id": f"comment-{client_request_id}",
                "body": body,
                "actor_id": actor_id,
            }
            conversation.setdefault("comments", []).append(comment)
            conversation["version"] = int(conversation["version"]) + 1
            self._append_activity(
                conversation,
                event_type="comment_added",
                actor={"type": "user", "id": actor_id},
                payload={"body": body, "visibility": "internal"},
            )
            result = {
                "comment": comment,
                "version": conversation["version"],
                "activity": deepcopy(conversation["activity"][-1]),
            }
            self._comment_commands[command_key] = deepcopy(result)
            return result

    def add_internal_comment(
        self,
        *,
        conversation_id: str,
        workspace_id: str,
        actor_id: str,
        body: str,
        expected_version: int,
    ) -> dict[str, object]:
        self.add_comment(
            conversation_id,
            body=body,
            actor_id=actor_id,
            client_request_id=f"internal-{conversation_id}-{expected_version}-{actor_id}",
            expected_version=expected_version,
            workspace_id=workspace_id,
        )
        return self.get_conversation(conversation_id)

    def list_events(
        self,
        *,
        workspace_id: str,
        conversation_id: str | None = None,
        after_sequence: int = 0,
    ) -> list[dict[str, object]]:
        with self._lock:
            events = []
            for conversation in self._conversations.values():
                if conversation["workspace_id"] != workspace_id:
                    continue
                if conversation_id is not None and conversation["id"] != conversation_id:
                    continue
                events.extend(
                    event
                    for event in conversation["activity"]
                    if int(event["sequence"]) > after_sequence
                )
            return deepcopy(events)

    def list_rules(self) -> list[dict[str, object]]:
        return deepcopy(_ASSIGNMENT_RULES)

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def message_count(self) -> int:
        return len(self._message_to_conversation)

    @property
    def activity_count(self) -> int:
        return sum(
            len(conversation["activity"])
            for conversation in self._conversations.values()
        )

    @staticmethod
    def _conversation_id(provider_thread_id: str) -> str:
        thread_suffix = provider_thread_id.removeprefix("thread-")
        return f"conversation-{thread_suffix}"

    @staticmethod
    def _new_conversation(
        conversation_id: str,
        event: NormalizedInboundEvent,
    ) -> dict[str, object]:
        message = {
            "id": f"message-{event.provider_message_id}",
            "event_id": event.event_id,
            "provider_account_id": event.provider_account_id,
            "provider_thread_id": event.provider_thread_id,
            "provider_message_id": event.provider_message_id,
            "connector": event.connector,
            "direction": event.direction,
            "sender": event.sender,
            "recipients": event.recipients,
            "subject": event.subject,
            "body_text": event.body_text,
            "occurred_at": event.occurred_at,
            "received_at": event.received_at,
            "raw_reference": event.raw_reference,
        }
        activity = {
            "id": f"activity-{event.event_id}",
            "type": "message_imported",
            "actor": {"type": "system", "id": None},
            "occurred_at": event.received_at,
            "sequence": 1,
            "payload": {
                "provider_account_id": event.provider_account_id,
                "provider_thread_id": event.provider_thread_id,
                "provider_message_id": event.provider_message_id,
            },
        }
        return {
            "id": conversation_id,
            "workspace_id": event.workspace_id,
            "channel": "email",
            "provider_account_id": event.provider_account_id,
            "provider_thread_id": event.provider_thread_id,
            "provider_message_id": event.provider_message_id,
            "status": "open",
            "priority": "unknown",
            "request_type": "unknown",
            "confidence": None,
            "classification": None,
            "owner_id": None,
            "queue_id": None,
            "assignment": None,
            "suggested_owner_id": None,
            "suggested_queue_id": None,
            "unassigned_reason": "No assignment has been evaluated.",
            "claim_state": "unclaimed",
            "claim": {"state": "unclaimed", "claimed_by": None},
            "active_viewer_id": None,
            "active_editor_id": None,
            "sla_state": "not_started",
            "version": 1,
            "subject": event.subject,
            "messages": [message],
            "comments": [],
            "assignment_history": [],
            "activity": [activity],
        }

    @staticmethod
    def _append_message(
        conversation: dict[str, object],
        event: NormalizedInboundEvent,
    ) -> None:
        conversation["messages"].append(
            {
                "id": f"message-{event.provider_message_id}",
                "event_id": event.event_id,
                "provider_account_id": event.provider_account_id,
                "provider_thread_id": event.provider_thread_id,
                "provider_message_id": event.provider_message_id,
                "connector": event.connector,
                "direction": event.direction,
                "sender": event.sender,
                "recipients": event.recipients,
                "subject": event.subject,
                "body_text": event.body_text,
                "occurred_at": event.occurred_at,
                "received_at": event.received_at,
                "raw_reference": event.raw_reference,
            }
        )

    @staticmethod
    def _append_activity(
        conversation: dict[str, object],
        *,
        event_type: str,
        actor: dict[str, str | None],
        payload: dict[str, object],
    ) -> None:
        sequence = len(conversation["activity"]) + 1
        conversation["activity"].append(
            {
                "id": f"activity-{conversation['id']}-{sequence}",
                "type": event_type,
                "actor": actor,
                "payload": deepcopy(payload),
                "occurred_at": "2026-08-09T00:00:00+00:00",
                "sequence": sequence,
            }
        )

    @staticmethod
    def _check_version(
        conversation: dict[str, object],
        expected_version: int,
    ) -> None:
        current_version = int(conversation["version"])
        if current_version != expected_version:
            raise VersionConflictError(
                expected_version=expected_version,
                current_version=current_version,
            )

    def _require_conversation(
        self,
        conversation_id: str,
        workspace_id: str | None = None,
    ) -> dict[str, object]:
        if conversation_id not in self._conversations:
            raise ConversationNotFoundError(conversation_id)
        conversation = self._conversations[conversation_id]
        if workspace_id is not None and conversation["workspace_id"] != workspace_id:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    @classmethod
    def _apply_fixture_intelligence(cls, conversation: dict[str, object]) -> None:
        classification = cls._classify(conversation)
        route = cls._suggest_route(str(classification["request_type"]))
        conversation["classification"] = classification
        conversation["request_type"] = classification["request_type"]
        conversation["priority"] = classification["priority"]
        conversation["confidence"] = classification["confidence"]
        conversation["suggested_queue_id"] = route["queue_id"]
        conversation["suggested_owner_id"] = route["owner_id"]
        conversation["unassigned_reason"] = (
            None if route["owner_id"] is not None else "No ordered rule supplied an owner."
        )
        conversation["assignment"] = {
            "queue_id": route["queue_id"],
            "owner_id": route["owner_id"],
            "source": "fixture_rule",
            "rule_id": route["rule_id"],
            "reason": route["reason"],
        }
        conversation["queue_id"] = route["queue_id"]
        conversation["owner_id"] = route["owner_id"]
        conversation["assignment_history"] = [
            {
                "previous": {"queue_id": None, "owner_id": None},
                "new": {
                    "queue_id": route["queue_id"],
                    "owner_id": route["owner_id"],
                },
                "reason": route["reason"],
                "source": "fixture_rule",
            }
        ]
        cls._append_activity(
            conversation,
            event_type="classified",
            actor={"type": "ai", "id": "fixture-classifier"},
            payload=classification,
        )
        cls._append_activity(
            conversation,
            event_type="assigned",
            actor={"type": "system", "id": "fixture-router"},
            payload=conversation["assignment"],
        )

    @staticmethod
    def _classify(conversation: dict[str, object]) -> dict[str, object]:
        message = conversation["messages"][-1]
        text = f"{message['subject']} {message['body_text']}".lower()
        if "delay" in text and "shipment" in text:
            classification = Classification(
                request_type="shipment_delay",
                priority="high",
                confidence=0.98,
                rationale=(
                    "The customer reports that shipment FT-204 has not arrived and "
                    "asks for a new delivery date."
                ),
                evidence_message_ids=[str(message["id"])],
            )
        else:
            classification = Classification(
                request_type="unknown",
                priority="unknown",
                confidence=0.35,
                rationale=(
                    "The fixture classifier could not identify a supported request type."
                ),
                evidence_message_ids=[str(message["id"])],
            )
        return asdict(classification)

    @staticmethod
    def _suggest_route(request_type: str) -> dict[str, object]:
        for rule in _ASSIGNMENT_RULES:
            if not rule["enabled"]:
                continue
            conditions = rule["conditions"]
            if conditions.get("request_type", request_type) == request_type:
                return {
                    "queue_id": "freight-operations",
                    "owner_id": "operator-freight",
                    "rule_id": "rule-freight-delay",
                    "reason": "Matched the first enabled shipment-delay fixture rule.",
                }
        return {
            "queue_id": "queue-unassigned",
            "owner_id": None,
            "rule_id": None,
            "reason": "No enabled assignment rule matched the request type.",
        }
