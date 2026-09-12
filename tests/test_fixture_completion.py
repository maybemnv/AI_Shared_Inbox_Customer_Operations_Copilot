from fastapi.testclient import TestClient

from app.fixture import create_demo_inbox
from app.main import create_app


def test_fixture_draft_failure_is_retryable_and_creates_no_draft():
    client = TestClient(create_app(create_demo_inbox()))

    failed = client.post(
        "/api/v1/conversations/conversation-ft-204/ai/run",
        json={"action": "draft", "failure_mode": "transient"},
    )
    conversation = client.get("/api/v1/conversations/conversation-ft-204")

    assert failed.status_code == 503
    assert failed.json()["code"] == "draft_generation_failed"
    assert failed.json()["retryable"] is True
    assert conversation.json()["draft"] is None


def test_fixture_draft_failure_retry_budget_is_enforced_by_api():
    client = TestClient(create_app(create_demo_inbox()))

    failures = [
        client.post(
            "/api/v1/conversations/conversation-ft-204/ai/run",
            json={"action": "draft", "failure_mode": "transient"},
        )
        for _ in range(4)
    ]

    assert [response.status_code for response in failures] == [503, 503, 503, 409]
    assert all(response.json()["retryable"] is True for response in failures[:3])
    assert failures[3].json()["code"] == "draft_retry_limit_exceeded"
    assert failures[3].json()["retryable"] is False


def test_fixture_secondary_read_models_are_available_without_live_connectors():
    client = TestClient(create_app(create_demo_inbox()))

    customer = client.get("/api/v1/customers/customer-jordan-lee")
    analytics = client.get("/api/v1/analytics")

    assert customer.status_code == 200
    assert customer.json()["name"] == "Jordan Lee"
    assert customer.json()["conversations"][0]["id"] == "conversation-ft-204"
    assert analytics.status_code == 200
    assert analytics.json()["mode"] == "fixture"
    assert analytics.json()["open_conversations"] == 1
