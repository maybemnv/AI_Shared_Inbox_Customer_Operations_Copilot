from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.fixture import build_freight_delay_event, create_demo_inbox
from app.ingestion import VersionConflictError
from app.main import create_app


def test_low_confidence_trace_stays_unassigned_and_does_not_invent_entities():
    inbox = create_demo_inbox()
    event = replace(
        build_freight_delay_event(),
        event_id="event-low-confidence",
        provider_thread_id="thread-low-confidence",
        provider_message_id="message-low-confidence",
        subject="Can you help with this request?",
        body_text="Can you help with this request?",
        sender={
            "external_id": None,
            "name": None,
            "address": "unknown@example.test",
        },
    )

    inbox.ingest(event)
    stored = inbox.get_conversation("conversation-low-confidence")

    assert stored["classification"]["request_type"] == "unknown"
    assert stored["classification"]["confidence"] == 0.35
    assert stored["assignment"]["queue_id"] == "queue-unassigned"
    assert stored["owner_id"] is None
    assert stored["unassigned_reason"] == (
        "No ordered rule supplied an owner."
    )
    assert stored["extracted_entities"] is None


def test_two_concurrent_assignments_allow_one_versioned_winner():
    inbox = create_demo_inbox()

    def assign(actor_id: str):
        try:
            return inbox.assign_conversation(
                "conversation-ft-204",
                owner_id=actor_id,
                queue_id="freight-operations",
                expected_version=1,
                actor_id=actor_id,
            )
        except Exception as exc:  # assert the exact conflict below
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(assign, ["operator-a", "operator-b"]))

    winners = [result for result in results if isinstance(result, dict)]
    conflicts = [result for result in results if isinstance(result, Exception)]
    assert len(winners) == 1
    assert len(conflicts) == 1
    assert isinstance(conflicts[0], VersionConflictError)
    assert inbox.get_conversation("conversation-ft-204")["version"] == 2


def test_stale_draft_edit_is_rejected_without_changing_current_body():
    inbox = create_demo_inbox()
    inbox.run_ai("conversation-ft-204", action="draft")
    draft = inbox.get_conversation("conversation-ft-204")["draft"]
    original_body = draft["body"]
    edited = inbox.edit_draft(
        draft["id"],
        body="Current operator response.",
        expected_version=draft["version"],
        actor_id="operator-a",
    )

    with pytest.raises(VersionConflictError):
        inbox.edit_draft(
            draft["id"],
            body="Stale operator response.",
            expected_version=draft["version"],
            actor_id="operator-b",
        )

    current = inbox.get_draft(draft["id"])
    assert edited["version"] == draft["version"] + 1
    assert current["body"] != original_body
    assert current["body"] == "Current operator response."


def test_workspace_scope_hides_conversations_and_drafts_from_other_workspaces():
    client = TestClient(create_app(create_demo_inbox()))
    generated = client.post(
        "/api/v1/conversations/conversation-ft-204/ai/run",
        json={"action": "draft"},
    )
    draft_id = generated.json()["draft"]["id"]

    conversation = client.get(
        "/api/v1/conversations/conversation-ft-204",
        params={"workspace_id": "other-workspace"},
    )
    draft = client.get(
        f"/api/v1/drafts/{draft_id}",
        params={"workspace_id": "other-workspace"},
    )

    assert conversation.status_code == 404
    assert conversation.json()["message"] == "conversation_not_found"
    assert draft.status_code == 404
    assert draft.json()["message"] == "draft_not_found"
