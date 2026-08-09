import pytest

from app.fixture import create_demo_inbox
from app.ingestion import VersionConflictError


def test_freight_case_classifies_and_returns_ordered_route_suggestion():
    inbox = create_demo_inbox()

    result = inbox.run_ai("conversation-ft-204", action="classify_and_route")

    assert result["state"] == "completed"
    assert result["classification"] == {
        "request_type": "shipment_delay",
        "priority": "high",
        "confidence": 0.98,
        "rationale": (
            "The customer reports that shipment FT-204 has not arrived and "
            "asks for a new delivery date."
        ),
        "evidence_message_ids": ["message-message-ft-204"],
    }
    assert result["route_suggestion"] == {
        "queue_id": "freight-operations",
        "owner_id": "operator-freight",
        "rule_id": "rule-freight-delay",
        "reason": "Matched the first enabled shipment-delay fixture rule.",
    }
    stored = inbox.get_conversation("conversation-ft-204")
    assert stored["queue_id"] == "freight-operations"
    assert stored["suggested_queue_id"] == "freight-operations"
    assert stored["suggested_owner_id"] == "operator-freight"


def test_stale_assignment_cannot_overwrite_newer_owner():
    inbox = create_demo_inbox()
    result = inbox.run_ai("conversation-ft-204", action="classify_and_route")
    current_version = result["version"]

    assigned = inbox.assign_conversation(
        "conversation-ft-204",
        owner_id="operator-a",
        queue_id="queue-freight-operations",
        expected_version=current_version,
        actor_id="operator-a",
    )

    with pytest.raises(VersionConflictError) as error:
        inbox.assign_conversation(
            "conversation-ft-204",
            owner_id="operator-b",
            queue_id="queue-freight-operations",
            expected_version=current_version,
            actor_id="operator-b",
        )

    assert error.value.current_version == assigned["version"]
    assert inbox.get_conversation("conversation-ft-204")["owner_id"] == "operator-a"


def test_claim_and_comment_are_replayable_through_activity_sequence():
    inbox = create_demo_inbox()

    claimed = inbox.claim_conversation(
        "conversation-ft-204",
        actor_id="operator-a",
        expected_version=1,
    )
    first_comment = inbox.add_comment(
        "conversation-ft-204",
        body="I am checking the latest carrier scan.",
        actor_id="operator-a",
        client_request_id="comment-1",
        expected_version=claimed["version"],
    )
    repeated_comment = inbox.add_comment(
        "conversation-ft-204",
        body="I am checking the latest carrier scan.",
        actor_id="operator-a",
        client_request_id="comment-1",
        expected_version=1,
    )

    assert first_comment["version"] == 3
    assert repeated_comment == first_comment
    events = inbox.list_events(
        workspace_id="demo-workspace",
        conversation_id="conversation-ft-204",
        after_sequence=3,
    )
    assert [event["type"] for event in events] == ["claimed", "comment_added"]
    assert events[-1]["payload"]["body"] == "I am checking the latest carrier scan."
