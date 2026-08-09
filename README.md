# AI Shared Inbox Customer Operations Copilot

This checkout contains the Phase 0/Phase 1 fixture-first vertical slice from
`PRD.md`. It exposes a small FastAPI read surface for the seeded freight-delay
conversation and proves normalized provider identity plus duplicate-event
safety.

## Local architecture

- Persistence: `InMemoryInbox` only. PostgreSQL is a reversible Phase 2+ choice,
  not configured here.
- Connector: the deterministic fixture is the only active connector. The
  normalized event uses the PRD's `gmail` connector value, but no OAuth or live
  provider behavior is claimed.
- AI/model: no model is configured. Classification, extraction, retrieval,
  summarization, and drafting remain future typed jobs; the Phase 1 read model
  intentionally reports unknown values.
- Queue/realtime: no queue or realtime product is configured. Ingestion is
  synchronous and the API returns a current snapshot so a future adapter can
  be introduced without changing the fixture contract.
- UI: not started in this slice. The shared root `design.md` will be applied
  when the Next.js surface begins.

## Run locally

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app.main:app --reload
```

The API is then available at `http://127.0.0.1:8000`.

## Phase 1 endpoints

- `GET /healthz` — process health.
- `GET /readyz` — explicit fixture-only dependency status.
- `GET /api/v1/conversations?workspace_id=demo-workspace` — seeded inbox list.
- `GET /api/v1/conversations/conversation-ft-204` — freight-delay detail.

The fixture is `fixtures/freight_delay.json` and represents the PRD case:
Jordan Lee, shipment `FT-204`, tracking `TRK-204`.
