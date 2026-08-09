from datetime import datetime, timezone

from app.fixture import build_freight_delay_event
from app.ingestion import InMemoryInbox


def test_freight_fixture_preserves_normalized_provider_identity():
    inbox = InMemoryInbox()
    event = build_freight_delay_event()

    result = inbox.ingest(event)

    assert result.accepted is True
    assert result.duplicate is False
    assert result.conversation_id == "conversation-ft-204"
    stored = inbox.get_conversation(result.conversation_id)
    assert stored["workspace_id"] == "demo-workspace"
    assert stored["channel"] == "email"
    assert stored["provider_thread_id"] == "thread-ft-204"
    assert stored["messages"][0]["provider_message_id"] == "message-ft-204"
    assert stored["messages"][0]["event_id"] == "event-ft-204"
    assert stored["messages"][0]["body_text"] == (
        "Our freight shipment FT-204 has not arrived. "
        "Please confirm the new delivery date."
    )


def test_replaying_same_event_does_not_create_duplicate_message_or_activity():
    inbox = InMemoryInbox()
    event = build_freight_delay_event()

    first = inbox.ingest(event)
    second = inbox.ingest(event)

    assert first.accepted is True
    assert second.accepted is False
    assert second.duplicate is True
    assert second.duplicate_reason == "event_id"
    assert inbox.event_count == 1
    assert inbox.message_count == 1
    assert inbox.activity_count == 1


def test_new_event_for_existing_provider_message_is_collision_safe():
    inbox = InMemoryInbox()
    original = build_freight_delay_event()
    replay = original.__class__(
        **{
            **original.__dict__,
            "event_id": "event-ft-204-retry",
            "received_at": datetime(2026, 8, 4, 12, 1, tzinfo=timezone.utc),
        }
    )

    first = inbox.ingest(original)
    second = inbox.ingest(replay)

    assert first.accepted is True
    assert second.accepted is False
    assert second.duplicate is True
    assert second.duplicate_reason == "provider_message_id"
    assert inbox.event_count == 1
    assert inbox.message_count == 1
    assert inbox.activity_count == 1
