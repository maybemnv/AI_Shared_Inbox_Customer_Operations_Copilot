# AI Shared Inbox Customer Operations Copilot — Demo Deployment

This guide describes the repeatable fixture deployment for client demos. It
does not claim production readiness, live connector access, live AI behavior,
or durable realtime guarantees.

## Target infrastructure

Supabase is the planned system of record: Postgres for workspaces, customers,
conversations, messages, assignments, drafts, approvals, SLA state, sync jobs,
and append-only activity events. Supabase Auth should own operator identity and
workspace access, with Storage reserved for explicitly approved attachments.
The current prototype uses an in-memory fixture store and must remain in fixture
mode until the schema, RLS, authorization, and reset behavior are implemented
and verified.

## Local fixture setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
Set-Location apps/web
npm install
npm run dev
```

Open `http://localhost:3000/inbox`. The API is available at
`http://127.0.0.1:8000`; `/healthz` and `/readyz` must report fixture mode.
Restarting the API resets the in-memory fixture state.

## Supabase setup boundary

1. Create a client-owned Supabase project and record its region, project ref,
   retention policy, backup plan, and access owners.
2. Add reviewed Postgres migrations for workspace-scoped inbox, activity,
   draft/approval, SLA, and sync state before selecting the Supabase backend.
3. Enable RLS and verify every read/write is scoped to the authenticated
   workspace. Keep service-role operations server-side only.
4. Configure secrets through the deployment platform, run migration and seed
   checks in staging, and rehearse reset/recovery before any client traffic.

## Environment and secrets

The current fixture path requires no secrets. Add values only after the code,
migrations, RLS policies, and authentication tests are complete.

| Variable | Purpose | Current status |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Browser API origin | Optional; local API default is used |
| `SUPABASE_URL` | Supabase project URL | Future; client supplies later |
| `SUPABASE_ANON_KEY` | Browser-safe Auth client key | Future; not used by current UI |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side migration/background access | Future secret; never commit or expose |
| `DATABASE_URL` | Supabase Postgres/pooling connection | Future; no durable DB is configured |
| `REDIS_URL` | Queue, locks, realtime/retry workers | Future; no queue is configured |
| `CONNECTOR_*` | Future email/provider credentials | Not configured; fixture connector only |

Never place secrets in `.env.example`, browser bundles, `tasks.md`, logs, or
Git history. The client adds secret values through the hosting secret store.

## Demo preflight

1. Start from a clean `master` checkout and run `python -m pytest -q`.
2. Confirm `/healthz` is `ok` and `/readyz` explicitly reports fixture-only
   dependencies.
3. Open `/inbox`, show the seeded freight-delay conversation, classification,
   evidence, owner/queue, SLA, draft, approval, and activity states.
4. Demonstrate edit → exact-version approval → separate fixture-only send.
5. Replay the inbound fixture, attempt a stale write, and show collision-safe
   or `version_conflict` recovery.
6. Exercise sync retry/quarantine and SLA warning/breach/escalation paths.

## Current limitations before go-live

- State is in memory; there is no Supabase persistence, migration, RLS,
  authentication, authorization, queue, or realtime transport.
- The connector, classification, extraction, retrieval, outbound send, SLA
  escalation, and retry paths are deterministic fixtures.
- Secondary route pages reuse the workbench shell; route-specific analytics,
  rules, customer, and integration views still need implementation.
- TLS, secret rotation, retention/deletion, observability, backups, incident
  recovery, and accessibility/reconnect acceptance remain outstanding.

## Handoff checklist

- [ ] Client owns Supabase project, billing, region, backups, Auth, RLS, and
  retention/deletion decisions.
- [ ] Implement and stage-test migrations, seed/reset, workspace isolation,
  audit durability, and authenticated operator access.
- [ ] Choose and verify one email connector; label all other providers fixture,
  blocked, or unknown.
- [ ] Add deployment health/readiness, logs, metrics, backups, TLS, and
  rollback/recovery procedures.
- [ ] Run accessibility, responsive, approval-safety, stale-write, retry,
  duplicate-event, and degraded-state acceptance traces from a clean checkout.
