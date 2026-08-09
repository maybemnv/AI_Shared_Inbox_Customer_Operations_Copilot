import pytest

from app.fixture import create_demo_inbox
from app.ingestion import ApprovalRequiredError, VersionConflictError


def test_freight_draft_contains_nullable_entities_bounded_context_and_evidence():
    inbox = create_demo_inbox()

    result = inbox.run_ai("conversation-ft-204", action="draft")

    assert result["state"] == "completed"
    stored = inbox.get_conversation("conversation-ft-204")
    assert stored["extracted_entities"] == {
        "customer_name": "Jordan Lee",
        "customer_external_id": None,
        "account_id": None,
        "order_id": None,
        "shipment_id": "FT-204",
        "tracking_number": "TRK-204",
        "requested_action": "Confirm the new delivery date",
        "promised_date": None,
        "confidence": 0.96,
        "evidence_message_ids": ["message-message-ft-204"],
        "unresolved_fields": ["account_id", "promised_date"],
    }
    assert stored["context"] == {
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
    assert stored["summary"] == {
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
        "next_action": "Check the carrier for a confirmed delivery date before promising one.",
        "evidence_message_ids": ["message-message-ft-204"],
    }
    assert stored["draft"]["state"] == "approval_required"
    assert stored["draft"]["missing_evidence"] == [
        "confirmed_delivery_date",
        "customer_account_record",
    ]
    assert all(
        evidence["source_type"] in {"message", "tracking_result"}
        for evidence in stored["draft"]["evidence"]
    )
    assert "new delivery date" not in stored["draft"]["body"].lower()


def test_draft_edit_invalidates_approval_and_exact_version_is_required_for_send():
    inbox = create_demo_inbox()
    inbox.run_ai("conversation-ft-204", action="draft")
    draft = inbox.get_conversation("conversation-ft-204")["draft"]

    approved = inbox.approve_draft(
        draft["id"],
        expected_version=draft["version"],
        actor_id="operator-a",
        workspace_id="demo-workspace",
    )
    assert approved["state"] == "approved"

    edited = inbox.edit_draft(
        draft["id"],
        body="Hi Jordan, we are checking the carrier for the latest delivery date.",
        expected_version=draft["version"],
        actor_id="operator-a",
        workspace_id="demo-workspace",
    )
    assert edited["version"] == draft["version"] + 1
    assert edited["state"] == "approval_required"
    assert edited["approval"] is None

    with pytest.raises(ApprovalRequiredError):
        inbox.send_draft(
            draft["id"],
            approval_id=approved["approval_id"],
            idempotency_key="send-ft-204-stale",
            actor_id="operator-a",
            workspace_id="demo-workspace",
        )

    with pytest.raises(VersionConflictError):
        inbox.approve_draft(
            draft["id"],
            expected_version=draft["version"],
            actor_id="operator-b",
            workspace_id="demo-workspace",
        )

    current = inbox.approve_draft(
        draft["id"],
        expected_version=edited["version"],
        actor_id="operator-a",
        workspace_id="demo-workspace",
    )
    sent = inbox.send_draft(
        draft["id"],
        approval_id=current["approval_id"],
        idempotency_key="send-ft-204-current",
        actor_id="operator-a",
        workspace_id="demo-workspace",
    )
    repeated = inbox.send_draft(
        draft["id"],
        approval_id=current["approval_id"],
        idempotency_key="send-ft-204-current",
        actor_id="operator-a",
        workspace_id="demo-workspace",
    )
    assert sent["state"] == "sent"
    assert sent["connector"] == "fixture_only"
    assert repeated == sent
    assert not [
        action
        for action in inbox.outbound_actions
        if action["idempotency_key"] == "send-ft-204-stale"
    ]


def test_new_inbound_message_invalidates_an_approved_draft():
    inbox = create_demo_inbox()
    inbox.run_ai("conversation-ft-204", action="draft")
    draft = inbox.get_conversation("conversation-ft-204")["draft"]
    approved = inbox.approve_draft(
        draft["id"],
        expected_version=draft["version"],
        actor_id="operator-a",
    )

    event = inbox._events[
        ("demo-workspace", "fixture-gmail-account", "event-ft-204")
    ]
    follow_up = event.__class__(
        **{
            **event.__dict__,
            "event_id": "event-ft-204-follow-up",
            "provider_message_id": "message-ft-204-follow-up",
            "occurred_at": "2026-08-04T13:00:00+00:00",
            "received_at": "2026-08-04T13:00:05+00:00",
            "subject": "Re: Shipment FT-204 is delayed",
            "body_text": "The carrier has another update for shipment FT-204.",
        }
    )

    inbox.ingest(follow_up)
    current = inbox.get_conversation("conversation-ft-204")

    assert approved["state"] == "approved"
    assert current["version"] == approved["conversation_version"] + 1
    assert current["draft"]["state"] == "approval_required"
    assert current["draft"]["approval"] is None
    assert current["draft"]["invalidated_reason"] == "new_inbound_message"
