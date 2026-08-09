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


def test_freight_fixture_has_typed_classification_with_message_evidence():
    inbox = InMemoryInbox()
    inbox.ingest(build_freight_delay_event())

    stored = inbox.get_conversation("conversation-ft-204")

    assert stored["classification"] == {
        "request_type": "shipment_delay",
        "priority": "high",
        "confidence": 0.98,
        "rationale": (
            "The customer reports that shipment FT-204 has not arrived and "
            "asks for a new delivery date."
        ),
        "evidence_message_ids": ["message-message-ft-204"],
    }
    assert stored["request_type"] == "shipment_delay"
    assert stored["priority"] == "high"
    assert [event["type"] for event in stored["activity"]] == [
        "message_imported",
        "classified",
        "assigned",
    ]


def test_fixture_assignment_uses_ordered_rule_and_records_reason():
    inbox = InMemoryInbox()
    inbox.ingest(build_freight_delay_event())

    stored = inbox.get_conversation("conversation-ft-204")

    assert stored["assignment"] == {
        "queue_id": "freight-operations",
        "owner_id": "operator-freight",
        "source": "fixture_rule",
        "rule_id": "rule-freight-delay",
        "reason": "Matched the first enabled shipment-delay fixture rule.",
    }
    assert stored["queue_id"] == "freight-operations"
    assert stored["owner_id"] == "operator-freight"
    assert stored["assignment_history"] == [
        {
            "previous": {"queue_id": None, "owner_id": None},
            "new": {"queue_id": "freight-operations", "owner_id": "operator-freight"},
            "reason": "Matched the first enabled shipment-delay fixture rule.",
            "source": "fixture_rule",
        }
    ]


def test_claim_requires_current_version_and_does_not_overwrite_newer_claim():
    inbox = InMemoryInbox()
    inbox.ingest(build_freight_delay_event())

    claimed = inbox.claim_conversation(
        conversation_id="conversation-ft-204",
        workspace_id="demo-workspace",
        actor_id="operator-a",
        expected_version=1,
    )

    assert claimed["version"] == 2
    assert claimed["claim"] == {
        "state": "claimed",
        "claimed_by": "operator-a",
    }

    try:
        inbox.claim_conversation(
            conversation_id="conversation-ft-204",
            workspace_id="demo-workspace",
            actor_id="operator-b",
            expected_version=1,
        )
    except Exception as exc:
        assert str(exc) == "version_conflict"
    else:
        raise AssertionError("stale claim unexpectedly succeeded")

    current = inbox.get_conversation("conversation-ft-204")
    assert current["version"] == 2
    assert current["claim"] == {"state": "claimed", "claimed_by": "operator-a"}


def test_internal_comment_appends_activity_without_mutating_prior_events():
    inbox = InMemoryInbox()
    inbox.ingest(build_freight_delay_event())

    before = inbox.get_conversation("conversation-ft-204")
    commented = inbox.add_internal_comment(
        conversation_id="conversation-ft-204",
        workspace_id="demo-workspace",
        actor_id="operator-a",
        body="I am checking the carrier update before replying.",
        expected_version=1,
    )

    assert commented["version"] == 2
    assert commented["activity"][0]["type"] == "message_imported"
    assert commented["activity"][:3] == before["activity"]
    assert commented["activity"][-1]["type"] == "comment_added"
    assert commented["activity"][-1]["actor"] == {
        "type": "user",
        "id": "operator-a",
    }
    assert commented["activity"][-1]["payload"] == {
        "body": "I am checking the carrier update before replying.",
        "visibility": "internal",
    }


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
    assert inbox.activity_count == 3


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
    assert inbox.activity_count == 3
