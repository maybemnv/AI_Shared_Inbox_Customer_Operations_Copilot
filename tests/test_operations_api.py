from fastapi.testclient import TestClient

from app.fixture import create_demo_inbox
from app.main import create_app


def new_client() -> TestClient:
    return TestClient(create_app(create_demo_inbox()))


def test_ai_route_assign_and_event_replay_commands_are_exposed():
    client = new_client()
    ai = client.post(
        "/api/v1/conversations/conversation-ft-204/ai/run",
        json={"action": "classify_and_route"},
    )
    assert ai.status_code == 200
    assert ai.json()["state"] == "completed"
    assert ai.json()["route_suggestion"]["queue_id"] == "freight-operations"
    version = ai.json()["version"]

    assigned = client.post(
        "/api/v1/conversations/conversation-ft-204/assign",
        json={
            "owner_id": "operator-a",
            "queue_id": "freight-operations",
            "expected_version": version,
            "actor_id": "operator-a",
        },
    )
    assert assigned.status_code == 200
    assert assigned.json()["owner_id"] == "operator-a"

    events = client.get(
        "/api/v1/events",
        params={
            "workspace_id": "demo-workspace",
            "conversation_id": "conversation-ft-204",
            "after_sequence": 1,
        },
    )
    assert events.status_code == 200
    assert events.json()["items"][-1]["type"] == "assigned"


def test_stale_assignment_returns_version_conflict_without_overwrite():
    client = new_client()
    ai = client.post(
        "/api/v1/conversations/conversation-ft-204/ai/run",
        json={"action": "classify"},
    )
    version = ai.json()["version"]
    current = client.post(
        "/api/v1/conversations/conversation-ft-204/assign",
        json={
            "owner_id": "operator-a",
            "queue_id": "freight-operations",
            "expected_version": version,
            "actor_id": "operator-a",
        },
    )
    assert current.status_code == 200

    stale = client.post(
        "/api/v1/conversations/conversation-ft-204/assign",
        json={
            "owner_id": "operator-b",
            "queue_id": "freight-operations",
            "expected_version": version,
            "actor_id": "operator-b",
        },
    )

    assert stale.status_code == 409
    assert stale.json()["code"] == "version_conflict"
    assert stale.json()["fields"]["current_version"] == str(current.json()["version"])


def test_comment_request_id_is_idempotent_and_rules_are_readable():
    client = new_client()
    comment = client.post(
        "/api/v1/conversations/conversation-ft-204/comments",
        json={
            "body": "Checking the latest carrier scan.",
            "actor_id": "operator-a",
            "client_request_id": "comment-api-1",
            "expected_version": 1,
        },
    )
    repeated = client.post(
        "/api/v1/conversations/conversation-ft-204/comments",
        json={
            "body": "Checking the latest carrier scan.",
            "actor_id": "operator-a",
            "client_request_id": "comment-api-1",
            "expected_version": 1,
        },
    )
    rules = client.get("/api/v1/rules")

    assert comment.status_code == 200
    assert repeated.status_code == 200
    assert repeated.json() == comment.json()
    assert rules.status_code == 200
    assert rules.json()["items"][0]["id"] == "rule-shipment-delay"
