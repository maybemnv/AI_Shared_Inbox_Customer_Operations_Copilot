# AI Shared Inbox Customer Operations Copilot

This checkout contains the verified fixture-first Phase 1 read slice, Phase 2
triage/collaboration slice, Phase 3 context/drafting slice, and the initial
Phase 4/5 demo workbench from `PRD.md`. It exposes a FastAPI surface and a
Next.js operator workbench for the seeded freight-delay conversation.

## Local architecture

- Persistence: `InMemoryInbox` only. PostgreSQL, durable audit storage, and
  migrations are not configured here.
- Connector: the deterministic fixture is the only active connector. The
  normalized event uses the PRD's `gmail` connector value, but no OAuth or live
  provider behavior is claimed.
- AI/model: no live model is configured. Classification, extraction, context,
  summary, and drafting use deterministic fixture rules; no live AI claim is
  made.
- Queue/realtime: no queue or realtime product is configured. Ingestion and
  fixture commands are synchronous and return current snapshots/activity.
- UI: `apps/web` is a Next.js workbench using the shared root `design.md` tokens
  and layout grammar. `/inbox` is the only completed route; secondary product
  areas remain planned and are not presented as completed navigation.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -B -m pytest -p no:cacheprovider -q
python -m ruff check --no-cache app tests
python -m uvicorn app.main:app --host 127.0.0.1 --port 8103

# In another terminal
Set-Location apps/web
npm ci
npm run build
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8103"
npm run dev -- --hostname 127.0.0.1 --port 3103
```

The API is available at `http://127.0.0.1:8103` and the workbench at
`http://127.0.0.1:3103/inbox`.

```powershell
Invoke-RestMethod http://127.0.0.1:8103/healthz
Invoke-RestMethod http://127.0.0.1:8103/readyz
Invoke-RestMethod http://127.0.0.1:8103/api/v1/demo/reset -Method Post
```

Reset is repeat-safe and affects only the in-memory fixture. No paid
credentials or live integrations are required. Stop both terminals with
`Ctrl+C`.

## Fixture endpoints

- `GET /healthz` - process health.
- `GET /readyz` - explicit fixture-only dependency status.
- `POST /api/v1/demo/reset` - reset only the in-memory fixture and reseed the
  canonical conversation.
- `GET /api/v1/conversations?workspace_id=demo-workspace` - seeded inbox list.
- `GET /api/v1/conversations/conversation-ft-204?workspace_id=demo-workspace` - detail.
- `POST /api/v1/conversations/{id}/ai/run` - deterministic fixture classification/routing.
- `POST /api/v1/conversations/{id}/assign` - expected-version operator assignment.
- `POST /api/v1/conversations/{id}/claim` - workspace-scoped expected-version claim.
- `POST /api/v1/conversations/{id}/comments` - internal comment plus activity output.
- `GET /api/v1/drafts/{id}` - workspace-scoped current draft.
- `PATCH /api/v1/drafts/{id}` - edit draft with an expected draft version.
- `POST /api/v1/drafts/{id}/approve` - approve the exact current draft version.
- `POST /api/v1/drafts/{id}/send` - fixture-only send after matching approval.
- `GET /api/v1/events?workspace_id=demo-workspace&conversation_id={id}` - activity replay.
- `GET /api/v1/rules` - ordered fixture assignment rules.

Command payloads carry `workspace_id`, `actor_id`, and `expected_version` where
applicable. A stale write returns `409` with `code=version_conflict` and does
not overwrite the current conversation or draft. A send without the matching
current approval returns `409` with `code=approval_required`. The fixture path
is synchronous and in-memory: it does not claim live AI, Supabase/PostgreSQL, queue,
realtime, provider, authentication, or durable persistence support.

The fixture is `fixtures/freight_delay.json` and represents the PRD case:
Jordan Lee, shipment `FT-204`, tracking `TRK-204`.
