# Production-ready repository baseline

Fixture runs use `APP_ENV=local-fixture` and `InMemoryInbox`. Staging and
production require `DATABASE_URL`, `QUEUE_PROVIDER=redis` or
`postgres-outbox`, and `AUTH_BEARER_TOKEN`; the API fails closed if any is
missing.

```powershell
psql "$env:DATABASE_URL" -f db/migrations/001_initial.sql
uv run uvicorn app.main:app --host 0.0.0.0 --port ${env:PORT ?? 8103}
```

The production repository persists the existing aggregate boundary in a
transaction-backed PostgreSQL snapshot, preserving draft-version, approval,
idempotency, retry, assignment, SLA, and audit state across restarts. The
normalized tables remain the SQL contract for the next reporting migration.
Provider connectors are disabled until authenticated workspace membership and
deployment secrets are supplied.
