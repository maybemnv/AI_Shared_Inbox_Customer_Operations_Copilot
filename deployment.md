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

## Repository deployment artifacts

- `.env.example` — non-secret local variable template.
- `db/migrations/001_initial.sql` — prepared Supabase/Postgres schema and RLS boundary; not applied by this checkout.
- `db/seed_freight_demo.sql` — durable-schema companion seed for `demo-workspace`; not run against a client project.
- `DEMO_SCRIPT.md` — exact client walkthrough and fixture reset path.
- `RUNBOOK.md` — sync, draft safety, SLA, Supabase handoff, and incident boundaries.

The migration and seed files are implementation artifacts, not evidence that a
Supabase project exists or that the live repository has been validated.

## Deployment topology boundary

The reversible target is a Supabase project for Postgres/Auth/Realtime, a
server-side FastAPI deployment for commands and provider credentials, and a
Next.js deployment for the operator UI. The specific FastAPI/Next.js hosting
platform, queue, worker runtime, domain, and TLS termination are not selected
in this prototype. Keep the fixture deployment as the fallback until each
boundary has an owner, secret, health check, rollback path, and acceptance run.

## Local fixture setup

The showcase is local and fixture-only. It does not require paid credentials,
Docker, Supabase, or a live provider. `POST /api/v1/demo/reset` clears only the
in-memory `InMemoryInbox` process and reseeds the canonical freight-delay event.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -B -m pytest -p no:cacheprovider -q
python -m ruff check --no-cache app tests
python -m uvicorn app.main:app --host 127.0.0.1 --port 8103
```

In a second terminal:

```powershell
Set-Location apps/web
npm ci
npm run build
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8103"
npm run dev -- --hostname 127.0.0.1 --port 3103
```

Open `http://127.0.0.1:3103/inbox`. The API is available at
`http://127.0.0.1:8103`; `/healthz` reports process health and `/readyz`
reports the seeded fixture conversation separately from unavailable durable
dependencies.

```powershell
Invoke-RestMethod http://127.0.0.1:8103/healthz
Invoke-RestMethod http://127.0.0.1:8103/readyz
Invoke-RestMethod http://127.0.0.1:8103/api/v1/demo/reset -Method Post
```

Reset is safe to repeat and affects only the running in-memory fixture. Stop
the API and web terminals with `Ctrl+C` when the walkthrough is complete.

For a non-default API origin, create `apps/web/.env.local` with
`NEXT_PUBLIC_API_BASE_URL=https://<api-host>`. The browser must never receive
`SUPABASE_SERVICE_ROLE_KEY` or a provider secret.

## Supabase setup boundary

1. Create a client-owned Supabase project and record its region, project ref,
   retention policy, backup plan, and access owners.
2. Add reviewed Postgres migrations for workspace-scoped inbox, activity,
   draft/approval, SLA, and sync state before selecting the Supabase backend.
3. Enable RLS and verify every read/write is scoped to the authenticated
   workspace. Keep service-role operations server-side only.
4. Apply `db/migrations/001_initial.sql`, review the generated policies, and
   run `db/seed_freight_demo.sql` only in a disposable/staging workspace.
5. Configure secrets through the deployment platform, run migration and seed
   checks in staging, and rehearse reset/recovery before any client traffic.
6. Implement the transaction-backed repository and run the contract suite
   against Supabase before changing `DEMO_MODE` from `fixture`.

## Environment and secrets

The current fixture path requires no secrets. Add values only after the code,
migrations, RLS policies, and authentication tests are complete.

| Variable | Purpose | Current status |
|---|---|---|
| `DEMO_MODE` | Select fixture or future durable mode | `fixture` only; no switch is wired |
| `API_HOST` / `API_PORT` | FastAPI bind address | Showcase command uses `127.0.0.1` / `8103` |
| `CORS_ALLOWED_ORIGINS` | Browser origins allowed to call the API | Local origins are hard-coded today; production config remains open |
| `NEXT_PUBLIC_API_BASE_URL` | Browser API origin | Showcase uses `http://127.0.0.1:8103` |
| `SUPABASE_URL` | Supabase project URL | Future; client supplies later |
| `SUPABASE_ANON_KEY` | Browser-safe Auth client key | Future; not used by current UI |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side migration/background access | Future secret; never commit or expose |
| `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Future browser Auth client | Future; not used by current UI |
| `DATABASE_URL` | Supabase Postgres/pooling connection | Future; no durable DB is configured |
| `REDIS_URL` | Queue, locks, realtime/retry workers | Future; no queue is configured |
| `CONNECTOR_*` | Future email/provider credentials | Not configured; fixture connector only |

Never place secrets in `.env.example`, browser bundles, `tasks.md`, logs, or
Git history. The client adds secret values through the hosting secret store.

## Demo preflight

1. Install `requirements-dev.txt` and run
   `python -B -m pytest -p no:cacheprovider -q`.
2. Run `python -m ruff check --no-cache app tests`.
3. From `apps/web`, run `npm ci`, `npm run build`, and `npm run test:e2e`.
4. Start API `8103` and web `3103`, then confirm `/healthz` is `ok` and
   `/readyz` reports the seeded conversation plus fixture-only dependencies.
5. POST `/api/v1/demo/reset`, then open `/inbox` and show the seeded freight-delay conversation, classification,
5. Open `/inbox`, show the seeded freight-delay conversation, classification,
   evidence, owner/queue, SLA, draft, approval, and activity states.
6. Demonstrate edit → exact-version approval → separate fixture-only send.
7. Replay the inbound fixture, attempt a stale write, and show collision-safe
   or `version_conflict` recovery.
8. Exercise sync retry/quarantine and SLA warning/breach/escalation paths.

## Current limitations before go-live

- State is in memory; there is no Supabase persistence, migration, RLS,
  authentication, authorization, queue, or realtime transport.
- The connector, classification, extraction, retrieval, outbound send, SLA
  escalation, and retry paths are deterministic fixtures.
- `db/migrations/001_initial.sql` and `db/seed_freight_demo.sql` are prepared
  but have not been run against a Supabase project from this checkout.
- `/inbox` is the only completed browser route; analytics, rules, customer, and
  integration views remain planned and are not presented as complete links.
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
