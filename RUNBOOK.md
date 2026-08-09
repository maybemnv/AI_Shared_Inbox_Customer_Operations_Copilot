# Prototype operations runbook

## Current operating mode

The supported client walkthrough is fixture-first. The FastAPI process uses
`InMemoryInbox`; the Next.js UI calls it over local CORS. Supabase/Postgres,
authentication, queue workers, realtime, and live connector credentials are
prepared as boundaries but are not wired or production-validated.

## Start, check, reset

```powershell
python -m pytest -q
python -m uvicorn app.main:app --reload --port 8000
cd apps/web
npm run build
npm run dev
```

- API health: `GET /healthz`
- Dependency honesty: `GET /readyz`
- Connector state: `GET /api/v1/connectors`
- Reset: stop and restart FastAPI; all fixture state is in memory.

## Sync and quarantine

Use `POST /api/v1/connectors/fixture-gmail/sync` with a stable
`idempotency_key`. A replay returns the same job result and reports the
duplicate count. A transient fixture failure may be retried using
`POST /api/v1/connectors/fixture-gmail/sync/{job_id}/retry`; a permanent
failure is quarantined and must not be force-retried. Inspect `state`,
`attempt`, `cursor`, `retryable`, and `failure_reason` before taking action.

## Draft and outbound safety

1. Generate a draft through the AI run command.
2. Edit with the current draft version.
3. Approve the exact current draft version.
4. Send only with the returned approval ID and a stable idempotency key.

An edit or new inbound event clears approval. Never create a second send key
to work around a conflict or ambiguous provider response. The local send
result is labelled `fixture_only` and is not an external delivery receipt.

## SLA and escalation

Start the SLA once with the current conversation version. Evaluate with an
explicit timestamp in the fixture demo. A breach creates one
`fixture_only` escalation event. Resolve with the current conversation version
after reviewing the activity history.

## Supabase handoff

1. Create a Supabase project and apply `db/migrations/001_initial.sql`.
2. Seed only a non-sensitive demo workspace with `db/seed_freight_demo.sql`.
3. Configure RLS and workspace JWT claims; verify a viewer cannot read another workspace.
4. Implement and test a transaction-backed repository before switching `DEMO_MODE` from `fixture`.
5. Move provider and service-role secrets to the deployment secret manager; never commit `.env`.
6. Re-run the contract, replay, approval-version, RLS, and outbound adapter tests against the project.

No production migration or secret has been run from this checkout.

## Incident boundaries

- API unavailable: stop the demo or use the direct fixture API; do not imply realtime recovery.
- Supabase/RLS failure: keep fixture mode enabled and block live-data access.
- Provider timeout: do not retry a non-idempotent write after an ambiguous result; inspect provider status first.
- Draft conflict: reload current conversation/draft, review evidence, edit, approve, then send with a new intentional idempotency key only when no outbound action was created.
