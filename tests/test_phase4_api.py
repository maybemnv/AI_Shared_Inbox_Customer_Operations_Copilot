from fastapi.testclient import TestClient

from app.fixture import create_demo_inbox
from app.main import create_app


def test_connector_sync_and_sla_commands_are_visible_through_api():
    client = TestClient(create_app(create_demo_inbox()))

    connectors = client.get("/api/v1/connectors")
    sync = client.post(
        "/api/v1/connectors/fixture-gmail/sync",
        json={"kind": "inbound", "idempotency_key": "api-sync-1"},
    )
    started = client.post(
        "/api/v1/conversations/conversation-ft-204/sla/start",
        json={"actor_id": "system-sla", "expected_version": 1},
    )
    breached = client.post(
        "/api/v1/conversations/conversation-ft-204/sla/evaluate",
        json={"now": "2026-08-09T01:05:00+00:00"},
    )
    resolved = client.post(
        "/api/v1/conversations/conversation-ft-204/resolve",
        json={
            "actor_id": "operator-a",
            "expected_version": breached.json()["version"],
        },
    )

    assert connectors.status_code == 200
    assert connectors.json()["items"][0]["live_status"] == "not_configured"
    assert sync.status_code == 200
    assert sync.json()["state"] == "completed"
    assert started.status_code == 200
    assert started.json()["sla_state"] == "running"
    assert breached.status_code == 200
    assert breached.json()["sla_state"] == "breached"
    assert breached.json()["escalation"]["connector"] == "fixture_only"
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
