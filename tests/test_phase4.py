from app.fixture import create_demo_inbox


def test_fixture_sync_has_cursor_replay_and_retry_quarantine_states():
    inbox = create_demo_inbox()

    connectors = inbox.list_connectors()
    completed = inbox.sync_connector(
        "fixture-gmail",
        kind="inbound",
        idempotency_key="sync-ft-204",
    )
    repeated = inbox.sync_connector(
        "fixture-gmail",
        kind="inbound",
        idempotency_key="sync-ft-204",
    )
    transient = inbox.sync_connector(
        "fixture-gmail",
        kind="inbound",
        idempotency_key="sync-transient",
        failure_mode="transient",
    )
    retried = inbox.retry_sync(transient["job_id"])
    quarantined = inbox.sync_connector(
        "fixture-gmail",
        kind="inbound",
        idempotency_key="sync-permanent",
        failure_mode="permanent",
    )
    blocked_retry = inbox.retry_sync(quarantined["job_id"])

    assert connectors == [
        {
            "id": "fixture-gmail",
            "connector": "gmail",
            "mode": "fixture",
            "status": "available",
            "live_status": "not_configured",
            "last_sync_at": None,
            "cursor": None,
            "capabilities": {
                "inbound": "fixture",
                "outbound": "fixture_only",
                "live": "not_configured",
            },
        }
    ]
    assert completed["state"] == "completed"
    assert completed["cursor"] == "fixture:event-ft-204"
    assert completed["duplicate_count"] == 1
    assert repeated == completed
    assert transient["state"] == "failed"
    assert transient["retryable"] is True
    assert transient["failure_reason"] == "fixture_transient_sync_failure"
    assert retried["state"] == "completed"
    assert retried["attempt"] == 2
    assert quarantined["state"] == "quarantined"
    assert quarantined["retryable"] is False
    assert quarantined["failure_reason"] == "fixture_permanent_sync_failure"
    assert blocked_retry["state"] == "quarantined"


def test_sla_warning_breach_has_one_fixture_escalation_and_can_resolve():
    inbox = create_demo_inbox()

    started = inbox.start_sla(
        "conversation-ft-204",
        expected_version=1,
        actor_id="system-sla",
    )
    warning = inbox.evaluate_sla(
        "conversation-ft-204",
        now="2026-08-09T00:50:00+00:00",
    )
    breached = inbox.evaluate_sla(
        "conversation-ft-204",
        now="2026-08-09T01:05:00+00:00",
    )
    repeated = inbox.evaluate_sla(
        "conversation-ft-204",
        now="2026-08-09T01:10:00+00:00",
    )
    resolved = inbox.resolve_conversation(
        "conversation-ft-204",
        expected_version=breached["version"],
        actor_id="operator-a",
    )

    assert started["sla_state"] == "running"
    assert started["sla"]["due_at"] == "2026-08-09T01:00:00+00:00"
    assert warning["sla_state"] == "warning"
    assert breached["sla_state"] == "breached"
    assert breached["escalation"]["connector"] == "fixture_only"
    assert breached["escalation"]["state"] == "sent"
    assert repeated["version"] == breached["version"]
    assert len(inbox.escalation_events) == 1
    assert resolved["status"] == "resolved"
    assert resolved["sla_state"] == "resolved"
