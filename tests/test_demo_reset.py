from dataclasses import replace

from fastapi.testclient import TestClient

from app.fixture import build_freight_delay_event, create_demo_inbox
from app.main import create_app


def test_demo_reset_is_repeatable_and_restores_seeded_baseline():
    inbox = create_demo_inbox()
    client = TestClient(create_app(inbox))

    claimed = client.post(
        "/api/v1/conversations/conversation-ft-204/claim",
        json={
            "workspace_id": "demo-workspace",
            "actor_id": "demo-operator",
            "expected_version": 1,
        },
    )
    assert claimed.status_code == 200
    assert claimed.json()["version"] == 2

    first_reset = client.post("/api/v1/demo/reset")
    second_reset = client.post("/api/v1/demo/reset")

    assert first_reset.status_code == 200
    assert second_reset.status_code == 200
    assert first_reset.json() == second_reset.json()
    assert first_reset.json() == {
        "status": "reset",
        "mode": "fixture",
        "workspace_id": "demo-workspace",
        "conversation_id": "conversation-ft-204",
    }

    conversation = client.get(
        "/api/v1/conversations/conversation-ft-204",
        params={"workspace_id": "demo-workspace"},
    )
    assert conversation.status_code == 200
    assert conversation.json()["version"] == 1
    assert conversation.json()["claim"] == {
        "state": "unclaimed",
        "claimed_by": None,
    }
    assert conversation.json()["draft"] is None


def test_demo_reset_clears_other_workspace_data_and_readyz_checks_seed():
    inbox = create_demo_inbox()
    inbox.ingest(
        replace(
            build_freight_delay_event(),
            workspace_id="another-workspace",
            event_id="event-other-workspace",
            provider_thread_id="thread-other-workspace",
            provider_message_id="message-other-workspace",
        )
    )
    client = TestClient(create_app(inbox))

    readiness = client.get("/readyz")
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "ready"
    assert readiness.json()["fixture"]["seeded_conversation"] == "conversation-ft-204"
    assert readiness.json()["fixture"]["seed_present"] is True

    assert client.get(
        "/api/v1/conversations",
        params={"workspace_id": "another-workspace"},
    ).json()["items"]

    first_reset = client.post("/api/v1/demo/reset")
    assert first_reset.status_code == 200
    assert client.get(
        "/api/v1/conversations",
        params={"workspace_id": "another-workspace"},
    ).json()["items"] == []

    after_reset = client.get("/readyz")
    assert after_reset.status_code == 200
    assert after_reset.json()["fixture"]["seed_present"] is True
