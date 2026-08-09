from fastapi.testclient import TestClient

from app.main import app


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
