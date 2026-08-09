from copy import deepcopy
from threading import RLock

from app.models import IngestResult, NormalizedInboundEvent


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
            self._conversations[conversation_id] = self._new_conversation(
                conversation_id,
                event,
            )

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
            "owner_id": None,
            "queue_id": None,
            "sla_state": "not_started",
            "version": 1,
            "subject": event.subject,
            "messages": [message],
            "activity": [activity],
        }
