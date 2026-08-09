from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.fixture import create_demo_inbox


client = TestClient(app)


def test_health_and_readiness_expose_fixture_only_dependencies():
    health = client.get("/healthz")
    readiness = client.get("/readyz")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "mode": "fixture"}
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "ready"
    assert readiness.json()["dependencies"]["database"] == "not_configured"
    assert readiness.json()["dependencies"]["provider"] == "fixture_only"


def test_conversation_read_surface_returns_seeded_freight_case():
    response = client.get(
        "/api/v1/conversations",
        params={"workspace_id": "demo-workspace", "channel": "email"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["next_cursor"] is None
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == "conversation-ft-204"
    assert payload["items"][0]["provider_message_id"] == "message-ft-204"


def test_missing_conversation_returns_prd_safe_error_contract():
    response = client.get("/api/v1/conversations/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"code", "message", "requestId", "retryable"}
    assert body["code"] == "not_found"
    assert body["message"] == "conversation_not_found"
    assert isinstance(body["requestId"], str) and body["requestId"]
    assert body["retryable"] is False


def test_claim_command_is_workspace_scoped_and_version_checked(monkeypatch):
    monkeypatch.setattr(main, "demo_inbox", create_demo_inbox())

    first = client.post(
        "/api/v1/conversations/conversation-ft-204/claim",
        json={
            "workspace_id": "demo-workspace",
            "actor_id": "operator-a",
            "expected_version": 1,
        },
    )
    stale = client.post(
        "/api/v1/conversations/conversation-ft-204/claim",
        json={
            "workspace_id": "demo-workspace",
            "actor_id": "operator-b",
            "expected_version": 1,
        },
    )
    wrong_workspace = client.post(
        "/api/v1/conversations/conversation-ft-204/claim",
        json={
            "workspace_id": "another-workspace",
            "actor_id": "operator-b",
            "expected_version": 2,
        },
    )

    assert first.status_code == 200
    assert first.json()["version"] == 2
    assert first.json()["claim"] == {
        "state": "claimed",
        "claimed_by": "operator-a",
    }
    assert stale.status_code == 409
    assert stale.json()["code"] == "version_conflict"
    assert stale.json()["currentVersion"] == 2
    assert wrong_workspace.status_code == 404
    assert wrong_workspace.json()["message"] == "conversation_not_found"

    current = client.get(
        "/api/v1/conversations/conversation-ft-204",
        params={"workspace_id": "demo-workspace"},
    )
    assert current.json()["version"] == 2
    assert current.json()["claim"]["claimed_by"] == "operator-a"


def test_internal_comment_returns_and_persists_append_only_activity(monkeypatch):
    monkeypatch.setattr(main, "demo_inbox", create_demo_inbox())

    response = client.post(
        "/api/v1/conversations/conversation-ft-204/comments",
        json={
            "workspace_id": "demo-workspace",
            "actor_id": "operator-a",
            "body": "I am checking the carrier update before replying.",
            "expected_version": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == 2
    assert payload["activity"]["type"] == "comment_added"
    assert payload["activity"]["actor"] == {
        "type": "user",
        "id": "operator-a",
    }
    assert payload["activity"]["payload"] == {
        "body": "I am checking the carrier update before replying.",
        "visibility": "internal",
    }

    detail = client.get("/api/v1/conversations/conversation-ft-204")
    assert detail.status_code == 200
    assert detail.json()["version"] == 2
    assert detail.json()["activity"][-1] == payload["activity"]
    assert len(detail.json()["activity"]) == 4
