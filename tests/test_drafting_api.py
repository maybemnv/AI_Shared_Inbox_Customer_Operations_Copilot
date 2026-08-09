from fastapi.testclient import TestClient

from app.fixture import create_demo_inbox
from app.main import create_app


def test_draft_edit_approval_and_send_api_are_separate_commands():
    client = TestClient(create_app(create_demo_inbox()))
    generated = client.post(
        "/api/v1/conversations/conversation-ft-204/ai/run",
        json={"action": "draft"},
    )
    assert generated.status_code == 200
    draft = generated.json()["draft"]

    edited = client.patch(
        f"/api/v1/drafts/{draft['id']}",
        json={
            "workspace_id": "demo-workspace",
            "actor_id": "operator-a",
            "body": "Hi Jordan, we are checking the carrier for the latest delivery date.",
            "expected_version": draft["version"],
        },
    )
    blocked = client.post(
        f"/api/v1/drafts/{draft['id']}/send",
        json={
            "workspace_id": "demo-workspace",
            "actor_id": "operator-a",
            "approval_id": "missing-approval",
            "idempotency_key": "blocked-send",
        },
    )
    approved = client.post(
        f"/api/v1/drafts/{draft['id']}/approve",
        json={
            "workspace_id": "demo-workspace",
            "actor_id": "operator-a",
            "expected_version": edited.json()["version"],
        },
    )
    sent = client.post(
        f"/api/v1/drafts/{draft['id']}/send",
        json={
            "workspace_id": "demo-workspace",
            "actor_id": "operator-a",
            "approval_id": approved.json()["approval_id"],
            "idempotency_key": "send-api-current",
        },
    )

    assert edited.status_code == 200
    assert edited.json()["state"] == "approval_required"
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "approval_required"
    assert approved.status_code == 200
    assert approved.json()["state"] == "approved"
    assert sent.status_code == 200
    assert sent.json()["state"] == "sent"
    assert sent.json()["connector"] == "fixture_only"
