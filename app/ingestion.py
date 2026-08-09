from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from threading import RLock

from app.models import Classification, ExtractedEntities, IngestResult, NormalizedInboundEvent


class VersionConflictError(Exception):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__("version_conflict")
        self.expected_version = expected_version
        self.current_version = current_version


class ConversationNotFoundError(Exception):
    pass


class ResourceNotFoundError(Exception):
    pass


class ApprovalRequiredError(Exception):
    def __init__(self, message: str = "current_draft_requires_exact_approval") -> None:
        super().__init__(message)


class EvidenceRequiredError(Exception):
    def __init__(self, missing_fields: list[str]) -> None:
        super().__init__("missing_evidence")
        self.missing_fields = missing_fields


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

_CONNECTOR_DEFINITIONS = [
    {
        "id": "fixture-gmail",
        "connector": "gmail",
        "mode": "fixture",
        "live_status": "not_configured",
        "capabilities": {
            "inbound": "fixture",
            "outbound": "fixture_only",
            "live": "not_configured",
        },
    }
]

_SLA_POLICY = {
    "id": "fixture-high-priority-response",
    "warning_at": "2026-08-09T00:45:00+00:00",
    "due_at": "2026-08-09T01:00:00+00:00",
}


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
        self._outbound_actions: dict[
            tuple[str, str, str], dict[str, object]
        ] = {}
        self._sync_jobs: dict[str, dict[str, object]] = {}
        self._sync_commands: dict[tuple[str, str], str] = {}
        self._connector_state: dict[str, dict[str, object]] = {
            definition["id"]: {
                "status": "available",
                "last_sync_at": None,
                "cursor": None,
            }
            for definition in _CONNECTOR_DEFINITIONS
        }
        self._escalation_events: list[dict[str, object]] = []
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
                draft = conversation.get("draft")
                if isinstance(draft, dict):
                    draft["state"] = "approval_required"
                    draft["approval"] = None
                    draft["invalidated_reason"] = "new_inbound_message"
                    draft["updated_at"] = event.received_at
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

    def get_conversation(
        self,
        conversation_id: str,
        workspace_id: str | None = None,
    ) -> dict[str, object] | None:
        with self._lock:
            conversation = self._conversations.get(conversation_id)
            if (
                conversation is not None
                and workspace_id is not None
                and conversation["workspace_id"] != workspace_id
            ):
                conversation = None
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
        if action not in {
            "classify",
            "classify_and_route",
            "route",
            "extract",
            "retrieve",
            "summarize",
            "draft",
        }:
            raise ValueError(f"unsupported_ai_action:{action}")

        with self._lock:
            conversation = self._require_conversation(conversation_id, workspace_id)
            if action in {"extract", "draft"}:
                self._ensure_extracted_entities(conversation)
            if action in {"retrieve", "summarize", "draft"}:
                self._ensure_context(conversation)
            if action in {"summarize", "draft"}:
                self._ensure_summary(conversation)

            if action == "draft":
                self._ensure_draft(conversation)
                return {
                    "job_id": f"job-{action}-{conversation_id}",
                    "state": "completed",
                    "input_version": conversation["version"],
                    "version": conversation["version"],
                    "extracted_entities": deepcopy(
                        conversation["extracted_entities"]
                    ),
                    "context": deepcopy(conversation["context"]),
                    "summary": deepcopy(conversation["summary"]),
                    "draft": deepcopy(conversation["draft"]),
                }

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

    def edit_draft(
        self,
        draft_id: str,
        *,
        body: str,
        expected_version: int,
        actor_id: str,
        workspace_id: str | None = None,
    ) -> dict[str, object]:
        with self._lock:
            conversation, draft = self._require_draft(draft_id, workspace_id)
            self._check_version(draft, expected_version)
            draft["body"] = body
            draft["version"] = int(draft["version"]) + 1
            draft["state"] = "approval_required"
            draft["approval"] = None
            draft["invalidated_reason"] = "draft_edited"
            draft["updated_at"] = "2026-08-09T00:00:00+00:00"
            self._append_activity(
                conversation,
                event_type="draft_edited",
                actor={"type": "user", "id": actor_id},
                payload={
                    "draft_id": draft_id,
                    "draft_version": draft["version"],
                },
            )
            conversation["version"] = int(conversation["version"]) + 1
            draft["conversation_version"] = conversation["version"]
            return deepcopy(draft)

    def approve_draft(
        self,
        draft_id: str,
        *,
        expected_version: int,
        actor_id: str,
        workspace_id: str | None = None,
    ) -> dict[str, object]:
        with self._lock:
            conversation, draft = self._require_draft(draft_id, workspace_id)
            self._check_version(draft, expected_version)
            self._validate_draft_evidence(draft)
            approval_id = f"approval-{draft_id}-v{draft['version']}"
            draft["state"] = "approved"
            draft["invalidated_reason"] = None
            draft["approval"] = {
                "approval_id": approval_id,
                "draft_version": draft["version"],
                "approved_by": actor_id,
                "approved_at": "2026-08-09T00:00:00+00:00",
            }
            draft["updated_at"] = "2026-08-09T00:00:00+00:00"
            self._append_activity(
                conversation,
                event_type="draft_approved",
                actor={"type": "user", "id": actor_id},
                payload={
                    "draft_id": draft_id,
                    "draft_version": draft["version"],
                    "approval_id": approval_id,
                },
            )
            conversation["version"] = int(conversation["version"]) + 1
            draft["conversation_version"] = conversation["version"]
            return {
                **deepcopy(draft["approval"]),
                "draft_id": draft_id,
                "state": draft["state"],
                "conversation_version": conversation["version"],
            }

    def send_draft(
        self,
        draft_id: str,
        *,
        approval_id: str,
        idempotency_key: str,
        actor_id: str,
        workspace_id: str | None = None,
    ) -> dict[str, object]:
        command_key = (workspace_id or "", draft_id, idempotency_key)
        with self._lock:
            if command_key in self._outbound_actions:
                return deepcopy(self._outbound_actions[command_key])
            conversation, draft = self._require_draft(draft_id, workspace_id)
            approval = draft.get("approval")
            if (
                draft.get("state") != "approved"
                or not isinstance(approval, dict)
                or approval.get("approval_id") != approval_id
                or approval.get("draft_version") != draft.get("version")
            ):
                raise ApprovalRequiredError()

            action = {
                "action_id": f"outbound-{draft_id}-v{draft['version']}",
                "workspace_id": conversation["workspace_id"],
                "conversation_id": conversation["id"],
                "draft_id": draft_id,
                "draft_version": draft["version"],
                "connector": "fixture_only",
                "approved_by": approval["approved_by"],
                "approved_at": approval["approved_at"],
                "requested_by": actor_id,
                "idempotency_key": idempotency_key,
                "provider_message_id": f"fixture-outbound-{draft_id}",
                "state": "sent",
                "sent_at": "2026-08-09T00:00:00+00:00",
            }
            self._outbound_actions[command_key] = deepcopy(action)
            self._append_activity(
                conversation,
                event_type="outbound_sent",
                actor={"type": "user", "id": actor_id},
                payload={
                    "draft_id": draft_id,
                    "draft_version": draft["version"],
                    "action_id": action["action_id"],
                    "connector": "fixture_only",
                },
            )
            conversation["version"] = int(conversation["version"]) + 1
            return deepcopy(action)

    @property
    def outbound_actions(self) -> list[dict[str, object]]:
        with self._lock:
            return deepcopy(list(self._outbound_actions.values()))

    def get_draft(
        self,
        draft_id: str,
        workspace_id: str | None = None,
    ) -> dict[str, object]:
        with self._lock:
            _, draft = self._require_draft(draft_id, workspace_id)
            return deepcopy(draft)

    def list_connectors(self) -> list[dict[str, object]]:
        with self._lock:
            return [
                {
                    **deepcopy(definition),
                    **deepcopy(self._connector_state[definition["id"]]),
                }
                for definition in _CONNECTOR_DEFINITIONS
            ]

    def sync_connector(
        self,
        connector_id: str,
        *,
        kind: str,
        idempotency_key: str,
        failure_mode: str | None = None,
    ) -> dict[str, object]:
        command_key = (connector_id, idempotency_key)
        with self._lock:
            if command_key in self._sync_commands:
                return deepcopy(self._sync_jobs[self._sync_commands[command_key]])
            self._require_connector(connector_id)
            job = {
                "job_id": f"sync-{connector_id}-{idempotency_key}",
                "connector_id": connector_id,
                "kind": kind,
                "idempotency_key": idempotency_key,
                "attempt": 1,
                "state": "queued",
                "retryable": False,
                "failure_reason": None,
                "cursor": None,
                "duplicate_count": 0,
            }
            if failure_mode == "transient":
                job.update(
                    {
                        "state": "failed",
                        "retryable": True,
                        "failure_reason": "fixture_transient_sync_failure",
                    }
                )
                self._connector_state[connector_id]["status"] = "failed"
            elif failure_mode == "permanent":
                job.update(
                    {
                        "state": "quarantined",
                        "retryable": False,
                        "failure_reason": "fixture_permanent_sync_failure",
                    }
                )
                self._connector_state[connector_id]["status"] = "quarantined"
            else:
                self._complete_fixture_sync(job)
            self._sync_jobs[job["job_id"]] = deepcopy(job)
            self._sync_commands[command_key] = job["job_id"]
            return deepcopy(job)

    def retry_sync(self, job_id: str) -> dict[str, object]:
        with self._lock:
            job = self._sync_jobs.get(job_id)
            if job is None:
                raise ResourceNotFoundError(job_id)
            if job["state"] != "failed" or job["retryable"] is not True:
                return deepcopy(job)
            job["attempt"] = int(job["attempt"]) + 1
            self._complete_fixture_sync(job)
            self._sync_jobs[job_id] = deepcopy(job)
            return deepcopy(job)

    def start_sla(
        self,
        conversation_id: str,
        *,
        expected_version: int,
        actor_id: str,
        workspace_id: str | None = None,
    ) -> dict[str, object]:
        with self._lock:
            conversation = self._require_conversation(conversation_id, workspace_id)
            self._check_version(conversation, expected_version)
            if conversation["sla_state"] != "not_started":
                return deepcopy(conversation)
            conversation["sla_state"] = "running"
            conversation["sla"] = {
                "policy_id": _SLA_POLICY["id"],
                "started_at": "2026-08-09T00:00:00+00:00",
                "warning_at": _SLA_POLICY["warning_at"],
                "due_at": _SLA_POLICY["due_at"],
                "last_evaluated_at": None,
            }
            self._append_activity(
                conversation,
                event_type="sla_started",
                actor={"type": "system", "id": actor_id},
                payload={
                    "policy_id": _SLA_POLICY["id"],
                    "due_at": _SLA_POLICY["due_at"],
                },
            )
            conversation["version"] = int(conversation["version"]) + 1
            return deepcopy(conversation)

    def evaluate_sla(
        self,
        conversation_id: str,
        *,
        now: str,
        workspace_id: str | None = None,
    ) -> dict[str, object]:
        with self._lock:
            conversation = self._require_conversation(conversation_id, workspace_id)
            sla = conversation.get("sla")
            if not isinstance(sla, dict) or conversation["sla_state"] == "resolved":
                return deepcopy(conversation)
            current = datetime.fromisoformat(now)
            due = datetime.fromisoformat(str(sla["due_at"]))
            warning = datetime.fromisoformat(str(sla["warning_at"]))
            sla["last_evaluated_at"] = now
            next_state = conversation["sla_state"]
            if current >= due:
                next_state = "breached"
            elif current >= warning and conversation["sla_state"] == "running":
                next_state = "warning"
            if next_state == conversation["sla_state"]:
                return deepcopy(conversation)
            conversation["sla_state"] = next_state
            if next_state == "breached" and conversation.get("escalation") is None:
                escalation = {
                    "id": f"escalation-{conversation_id}",
                    "conversation_id": conversation_id,
                    "connector": "fixture_only",
                    "channel": "fixture",
                    "state": "sent",
                    "idempotency_key": f"sla-{conversation_id}",
                    "reason": "High-priority response SLA breached.",
                }
                conversation["escalation"] = escalation
                self._escalation_events.append(deepcopy(escalation))
                self._append_activity(
                    conversation,
                    event_type="sla_escalated",
                    actor={"type": "system", "id": "fixture-sla"},
                    payload=escalation,
                )
            conversation["version"] = int(conversation["version"]) + 1
            return deepcopy(conversation)

    def resolve_conversation(
        self,
        conversation_id: str,
        *,
        expected_version: int,
        actor_id: str,
        workspace_id: str | None = None,
    ) -> dict[str, object]:
        with self._lock:
            conversation = self._require_conversation(conversation_id, workspace_id)
            self._check_version(conversation, expected_version)
            conversation["status"] = "resolved"
            conversation["sla_state"] = "resolved"
            conversation["resolved_at"] = "2026-08-09T00:00:00+00:00"
            self._append_activity(
                conversation,
                event_type="resolved",
                actor={"type": "user", "id": actor_id},
                payload={"status": "resolved"},
            )
            conversation["version"] = int(conversation["version"]) + 1
            return deepcopy(conversation)

    @property
    def escalation_events(self) -> list[dict[str, object]]:
        with self._lock:
            return deepcopy(self._escalation_events)

    @staticmethod
    def _require_connector(connector_id: str) -> None:
        if connector_id not in {definition["id"] for definition in _CONNECTOR_DEFINITIONS}:
            raise ResourceNotFoundError(connector_id)

    def _complete_fixture_sync(self, job: dict[str, object]) -> None:
        from app.fixture import build_freight_delay_event

        result = self.ingest(build_freight_delay_event())
        job.update(
            {
                "state": "completed",
                "retryable": False,
                "failure_reason": None,
                "cursor": "fixture:event-ft-204",
                "duplicate_count": 1 if result.duplicate else 0,
            }
        )
        self._connector_state[job["connector_id"]].update(
            {
                "status": "available",
                "last_sync_at": "2026-08-09T00:00:00+00:00",
                "cursor": job["cursor"],
            }
        )

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
            "sla": None,
            "escalation": None,
            "version": 1,
            "subject": event.subject,
            "messages": [message],
            "comments": [],
            "assignment_history": [],
            "extracted_entities": None,
            "context": None,
            "summary": None,
            "draft": None,
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

    def _require_draft(
        self,
        draft_id: str,
        workspace_id: str | None = None,
    ) -> tuple[dict[str, object], dict[str, object]]:
        for conversation in self._conversations.values():
            draft = conversation.get("draft")
            if isinstance(draft, dict) and draft.get("id") == draft_id:
                if (
                    workspace_id is not None
                    and conversation["workspace_id"] != workspace_id
                ):
                    break
                return conversation, draft
        raise ResourceNotFoundError(draft_id)

    @classmethod
    def _ensure_extracted_entities(cls, conversation: dict[str, object]) -> None:
        if conversation.get("extracted_entities") is not None:
            return
        entities = cls._extract_entities(conversation)
        conversation["extracted_entities"] = entities
        cls._append_activity(
            conversation,
            event_type="entities_extracted",
            actor={"type": "ai", "id": "fixture-extractor"},
            payload=entities,
        )
        conversation["version"] = int(conversation["version"]) + 1

    @classmethod
    def _ensure_context(cls, conversation: dict[str, object]) -> None:
        if conversation.get("context") is not None:
            return
        conversation["context"] = cls._retrieve_context(conversation)

    @classmethod
    def _ensure_summary(cls, conversation: dict[str, object]) -> None:
        if conversation.get("summary") is not None:
            return
        summary = cls._summarize(conversation)
        conversation["summary"] = summary
        cls._append_activity(
            conversation,
            event_type="summary_created",
            actor={"type": "ai", "id": "fixture-summarizer"},
            payload=summary,
        )
        conversation["version"] = int(conversation["version"]) + 1

    @classmethod
    def _ensure_draft(cls, conversation: dict[str, object]) -> None:
        if conversation.get("draft") is not None:
            return
        draft = cls._build_draft(conversation)
        conversation["draft"] = draft
        cls._append_activity(
            conversation,
            event_type="draft_created",
            actor={"type": "ai", "id": "fixture-drafter"},
            payload={
                "draft_id": draft["id"],
                "draft_version": draft["version"],
                "evidence_count": len(draft["evidence"]),
                "missing_evidence": draft["missing_evidence"],
            },
        )
        conversation["version"] = int(conversation["version"]) + 1
        draft["conversation_version"] = conversation["version"]

    @staticmethod
    def _extract_entities(conversation: dict[str, object]) -> dict[str, object]:
        message = conversation["messages"][-1]
        body = str(message["body_text"])
        shipment_id = "FT-204" if "FT-204" in body else None
        tracking_number = "TRK-204" if shipment_id == "FT-204" else None
        entities = ExtractedEntities(
            customer_name=message["sender"]["name"],
            customer_external_id=message["sender"]["external_id"],
            account_id=None,
            order_id=None,
            shipment_id=shipment_id,
            tracking_number=tracking_number,
            requested_action="Confirm the new delivery date"
            if "delivery date" in body.lower()
            else None,
            promised_date=None,
            confidence=0.96 if shipment_id is not None else 0.35,
            evidence_message_ids=[str(message["id"])],
            unresolved_fields=["account_id", "promised_date"]
            if shipment_id is not None
            else ["account_id", "shipment_id", "tracking_number"],
        )
        return asdict(entities)

    @staticmethod
    def _retrieve_context(conversation: dict[str, object]) -> dict[str, object]:
        entities = conversation["extracted_entities"]
        if not isinstance(entities, dict) or entities.get("tracking_number") != "TRK-204":
            return {
                "state": "missing",
                "items": [],
                "missing": ["tracking_record", "customer_account_record"],
            }
        return {
            "state": "available",
            "items": [
                {
                    "source_type": "tracking_result",
                    "source_id": "tracking-TRK-204",
                    "label": "TRK-204 carrier timeline",
                    "captured_at": "2026-08-04T12:05:00+00:00",
                    "data": {
                        "tracking_number": "TRK-204",
                        "status": "delayed",
                        "last_scan": "Memphis, TN",
                        "estimated_delivery": None,
                    },
                }
            ],
            "missing": ["customer_account_record", "confirmed_delivery_date"],
        }

    @staticmethod
    def _summarize(conversation: dict[str, object]) -> dict[str, object]:
        return {
            "issue": "Shipment FT-204 is delayed.",
            "ask": "Confirm the new delivery date.",
            "known_facts": [
                "Shipment FT-204 has not arrived.",
                "Tracking TRK-204 is marked delayed after a last scan in Memphis, TN.",
            ],
            "missing_facts": [
                "A customer account record is not linked.",
                "A confirmed delivery date is not available.",
            ],
            "next_action": (
                "Check the carrier for a confirmed delivery date before promising one."
            ),
            "evidence_message_ids": [conversation["messages"][-1]["id"]],
        }

    @staticmethod
    def _build_draft(conversation: dict[str, object]) -> dict[str, object]:
        message = conversation["messages"][-1]
        return {
            "id": f"draft-{conversation['id']}",
            "conversation_id": conversation["id"],
            "conversation_version": conversation["version"],
            "version": 1,
            "channel": "email",
            "recipient": message["sender"]["address"],
            "subject": f"Re: {message['subject']}",
            "body": (
                "Hi Jordan,\n\n"
                "I’m sorry that shipment FT-204 has been delayed. We’re checking "
                "with the carrier for a confirmed delivery date and will follow up "
                "as soon as we have one.\n\n"
                "Best,\nFreight Operations"
            ),
            "evidence": [
                {
                    "source_type": "message",
                    "source_id": message["id"],
                    "label": "Jordan Lee's shipment delay email",
                    "captured_at": message["received_at"],
                },
                {
                    "source_type": "tracking_result",
                    "source_id": "tracking-TRK-204",
                    "label": "TRK-204 carrier timeline",
                    "captured_at": "2026-08-04T12:05:00+00:00",
                },
            ],
            "missing_evidence": [
                "confirmed_delivery_date",
                "customer_account_record",
            ],
            "confidence": 0.91,
            "state": "approval_required",
            "approval": None,
            "invalidated_reason": None,
            "generated_at": "2026-08-09T00:00:00+00:00",
            "updated_at": "2026-08-09T00:00:00+00:00",
        }

    @staticmethod
    def _validate_draft_evidence(draft: dict[str, object]) -> None:
        body = str(draft["body"]).lower()
        if "confirmed delivery date is" in body:
            raise EvidenceRequiredError(["confirmed_delivery_date"])

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
        for rule in sorted(_ASSIGNMENT_RULES, key=lambda item: item["priority"]):
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
