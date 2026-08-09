# AI Shared Inbox and Customer Operations Copilot — Client Demo Prototype Tasks

**Goal:** Build a fixture-first, human-controlled operations workspace that classifies a freight-delay conversation, assigns ownership, drafts an evidence-backed response, tracks the SLA, and proves collision-safe recovery.

**Architecture:** Use the PRD boundaries: Next.js workspace, FastAPI command/query API, PostgreSQL system of record, queue-backed workers, persisted activity events, realtime updates, and provider adapters. The deterministic fixture path is the primary demo path; one live connector is optional and must be capability-verified.

**Tech stack:** Next.js, FastAPI, PostgreSQL, message queue, realtime updates, background sync, and typed provider adapters, as specified in `PRD.md`.

## Current status - 2026-08-09

### Verified delivered in the fixture-first Phase 1/Phase 2/Phase 3/Phase 4/Phase 5 slices

- [x] Added a fixture-first inbound envelope and seeded freight-delay case for Jordan Lee, shipment `FT-204`, and tracking `TRK-204`.
- [x] Implemented stable provider/thread/message/event identities with replay and provider-message collision protection.
- [x] Added a workspace-scoped FastAPI inbox read surface with conversation detail, source metadata, activity history, health, readiness, and safe not-found responses.
- [x] Added regression coverage for identity normalization, replay safety, collision safety, workspace scope, readiness, and read-model API behavior.
- [x] Documented the fixture-only boundary, local setup, and unverified production integrations.
- [x] Added typed deterministic freight-delay classification with intent, priority, bounded confidence, rationale, and evidence message IDs.
- [x] Added ordered fixture routing with queue, owner, fallback, assignment reason, assignment history, and `classified`/`assigned` activity events.
- [x] Added workspace-scoped claim and assignment commands with expected-version conflict responses that preserve newer state.
- [x] Added internal comments with client-request replay safety and append-only `comment_added` activity output.
- [x] Added focused Phase 2/fixture-drafting and client acceptance regression tests; the current local suite verifies 31 passing tests.
- [x] Added fixture-only nullable entity extraction, bounded tracking context, summary, evidence references, and missing-evidence state.
- [x] Added fixture-only draft edit, exact-version approval, approval invalidation after edits/new inbound, and idempotent send-boundary tests.
- [x] Added separate draft API commands for edit, approve, and send; send returns `fixture_only` and makes no live provider claim.
- [x] Added fixture connector status, cursor-based sync replay, transient retry, permanent quarantine, and operator-visible failure reasons.
- [x] Added deterministic SLA start, warning, breach, one idempotent `fixture_only` escalation, and resolve commands.
- [x] Added a Next.js workbench with the shared token palette, floating-pill navigation, stat strip, triage list, detail thread, context rail, draft controls, activity, and degraded API state.
- [x] Added `deployment.md` with Supabase target infrastructure, fixture launch steps, environment-variable ownership, demo preflight, and explicit no-secrets limitations.

### Not yet complete

- [ ] PostgreSQL migrations, durable workers, queue/realtime transport, authentication, authorization, and persisted audit storage remain outstanding.
- [ ] Two-client realtime/reconnect behavior, durable persistence, and authentication/authorization remain outstanding beyond this fixture contract.
- [ ] Durable evidence/provider retrieval, production outbound sending, and live connector validation remain outstanding.
- [ ] Supabase schema/RLS, durable sync workers, route-specific secondary views, realtime reconnect behavior, complete accessibility review, and the full draft state machine remain outstanding.

### Next work queue

1. Add acceptance traces, Supabase migrations/RLS, and workspace/concurrency/security contracts.
2. Add route-specific secondary views, realtime updates, reconnect replay, and complete UI state coverage.
3. Rehearse the demo script/runbook and validate the prepared Supabase schema/RLS in a client-owned staging project without adding client secrets here.
4. Validate one provider only if credentials and behavior are proven; preserve the fixture fallback.

The full checklist below remains the source of the complete Phase 0-6 scope; this status records only verified work in the current checkout.

## Global constraints

- [ ] Preserve the PRD human-control boundary: classification, extraction, retrieval, summarization, routing, and drafting may run asynchronously; outbound sending requires explicit approval of the exact current draft version followed by a separate send action.
- [ ] Treat the checkout as greenfield. All application, test, fixture, configuration, deployment, and operational files below are proposed work.
- [ ] Use deterministic fixtures for the canonical demo and label every live, fixture-backed, blocked, and unknown integration state in the UI.
- [ ] Do not claim provider scopes, model versions, queue behavior, realtime guarantees, retention, compliance, or production readiness until verified.
- [ ] Use `D:\ARC Automation Service\design.md` as the shared visual authority for genre, shell, palette, typography, spacing, shape, motion, and explicit states. Adapt its visual grammar to inbox semantics; do not copy call or revenue content.
- [ ] Keep the PRD out-of-scope boundary: no autonomous outbound sending, omnichannel parity, voice/video workflows, payments, scheduling, order modification, customer portal, billing, or production certification for every connector.

## Target file structure

- Create `apps/web/` for the Next.js workspace, routes, components, tokens, and typed client.
- Create `apps/api/` for FastAPI routes, schemas, services, authorization, and integration interfaces.
- Create `workers/` for sync, intelligence, outbound, SLA, retry, and quarantine jobs.
- Create `db/migrations/` and `db/seed_freight_demo.sql` for the system of record and canonical fixture.
- Create `tests/contracts/`, `tests/traces/`, `tests/concurrency/`, and `tests/security/` for contract, trace, race, and safety coverage.
- Create `README.md`, `.env.example`, `DEMO_SCRIPT.md`, and `RUNBOOK.md` for repeatable client operation.

## Phase 0 — Demo contract and foundation

- [ ] Convert PRD Traces 1–3 and metrics M-01–M-10 into the acceptance checklist in `tests/acceptance/demo_contract.md`.
- [ ] Scaffold the web, API, worker, database, connector, and test boundaries without committing secrets or unverified provider versions.
- [ ] Define workspace-scoped authentication and authorization interfaces before exposing conversation reads or commands.
- [ ] Define typed envelopes for normalized inbound events, activity events, command request IDs, correlation IDs, and safe API errors.
- [ ] Add health/readiness checks for API, database, queue, workers, and realtime transport; expose dependency state honestly.

**Exit gate:** A clean checkout starts locally, health checks are readable, and the demo can run entirely from fixtures.

## Phase 1 — Deterministic inbox thin slice

- [ ] Create workspace, connector, customer, conversation, message, activity-event, and sync-job migrations with workspace scope and uniqueness constraints.
- [ ] Seed the canonical freight case: Jordan Lee, `Shipment FT-204 is delayed`, shipment `FT-204`, tracking `TRK-204`, and the expected source metadata.
- [x] Normalize fixture inbound events with provider, thread, message, and event identities; acknowledge duplicate events without creating duplicate messages or activities.
- [ ] Implement `GET /inbox` and `GET /inbox/{conversation_id}` with filters for status, queue, owner, priority, SLA state, and channel.
- [x] Build the initial inbox row, conversation detail, latest message, source metadata, and append-only activity timeline.
- [ ] Render explicit loading, empty, unavailable, stale, and error states rather than blank surfaces.
- [x] Add contract tests for event identity, message identity, workspace scope, replay, and safe error responses.

**Demo gate:** The seeded freight conversation appears once with stable IDs, source metadata, and a visible activity timeline.

## Phase 2 — Triage, routing, ownership, and collaboration

- [x] Implement typed deterministic fixture request classification, priority, confidence, rationale, and evidence message IDs.
- [x] Implement ordered fixture assignment rules, queue fallback, owner assignment, assignment history, and an explicit assignment reason.
- [x] Implement fixture claim state, active viewer/editor state, expected-version writes, and `version_conflict` responses that never overwrite newer state.
- [x] Implement internal comments and append-only fixture activity events; durable persistence remains outstanding.
- [ ] Stream assignment, claim, comment, and activity updates to two authorized open clients; replay persisted events after reconnect.
- [ ] Add classification, routing, duplicate-event, stale-write, and two-client concurrency tests.

**Demo gate:** Two operators can open the same conversation, claim it, see the live update, receive `version_conflict` on a stale edit, reload, and continue safely.

## Phase 3 — Context, intelligence, and safe drafting

- [x] Implement fixture-only nullable extraction for customer, account, order, shipment, tracking, promised date, and requested action; null means unknown and never an invented fact.
- [x] Implement fixture-only bounded tracking retrieval with a source timestamp and evidence reference; account, CRM, and order adapters remain outstanding.
- [x] Implement fixture-only summaries containing issue, customer ask, known facts, missing facts, and next action.
- [ ] Build the context rail for customer, account, shipment/order, CRM records, source references, and confidence rationale.
- [ ] Implement the full draft state machine: `generating`, `ready`, `edited`, `approval_required`, `approved`, and `send_failed`; the current fixture path covers `edited`, `approval_required`, and `approved`.
- [x] Increment fixture draft versions on every edit; invalidate approval after edits or a new inbound message.
- [x] Prevent the tested unsupported delivery-date claim and expose missing evidence before fixture approval.
- [x] Add tests proving no fixture outbound command can be created without approval for the exact current draft version.

**Demo gate:** The freight case produces an editable evidence-backed draft, shows missing evidence honestly, and keeps send locked until exact-version approval.

## Phase 4 — SLA, sync, and one validated connector

- [x] Implement fixture-only sync with cursor/watermark state, retry classification, quarantine, operator-visible failure reason, and replay safety.
- [ ] Validate one listed email/shared-inbox connector end to end; keep all other connectors behind the normalized adapter contract and capability matrix.
- [x] Implement fixture-only SLA policy selection, start, due time, warning, breach, resolution, and one idempotent escalation event.
- [x] Keep escalation as an explicitly labeled `fixture_only` event; validate Slack only if scopes and behavior are proven.
- [ ] Add inbound and approved-outbound adapter contract tests, including provider failure, timeout, duplicate callback, and unsupported-operation cases.
- [x] Scaffold `/settings/integrations`; connector status, last sync, retry, quarantine, and live/fixture labels are available through the API and remain to be composed into a dedicated settings view.

**Demo gate:** Either one connector completes the canonical path, or the fixture path remains primary and all provider gaps are visible rather than implied to work.

## Phase 5 — UI and shared design system

- [x] Apply the root `design.md` schema: modern-minimal, quiet technical workbench; stat strip; review surface; supporting panels; content-sized floating-pill navigation; inline-rule footer.
- [x] Use the shared brand tokens `--brand-silver`, `--brand-steel`, `--brand-blue`, `--brand-gray`, `--brand-soft`, `--brand-slate`, `--brand-ink`, and `--brand-white`.
- [x] Use Trebuchet MS for display, Segoe UI/Arial for body, and Consolas or `ui-monospace` for IDs, timestamps, and event data.
- [x] Use a 4-point spacing base, visible 1px rules, restrained rounded corners, no gradients or glass effects, single-line controls, visible focus, and reduced motion.
- [x] Scaffold the PRD routes `/inbox`, `/inbox/{conversationId}`, `/customers/{customerId}`, `/rules`, `/analytics`, and `/settings/integrations`.
- [x] Implement the initial conversation rows, assignment, confidence, SLA, AI actions, draft, context, activity, connector, and API-unavailable states in the workbench.
- [ ] Complete route-specific secondary views, collision/reconnect/stale-data UI, keyboard/focus review, screen-reader review, 390px device rehearsal, and skeleton loading.
- [ ] Do not invent call or revenue metrics; show only persisted conversation, SLA, collaboration, sync, AI, and outbound facts.

**Exit gate:** A client can understand owner, queue, priority, evidence, approval state, and SLA state without hidden system state.

## Phase 6 — Validation, rehearsal, and client handoff

- [ ] Run contract, persistence, workspace-authorization, idempotency, concurrency, approval-version, SLA, sync-retry, and outbound-safety tests.
- [ ] Execute the freight-delay trace, duplicate-event/collision trace, and low-confidence/missing-account trace from clean fixtures.
- [ ] Instrument M-01–M-10 from persisted events; keep M-10 qualitative and show denominators for numeric metrics.
- [ ] Add correlation IDs, audit completeness checks, retry/quarantine inspection, and degraded AI/realtime behavior.
- [x] Add `README.md` with startup, fixture seed/reset, demo mode, tests, environment variables, and known limitations.
- [x] Add `DEMO_SCRIPT.md` with preflight, exact click path, expected states, live-vs-fixture callouts, and fallback steps.
- [x] Add `RUNBOOK.md` with connector setup, secrets handling, redacted logs, sync/retry operations, escalation, retention assumptions, and incident recovery.
- [x] Add `deployment.md` with Supabase target infrastructure, fixture launch, environment variables, health checks, rollback boundary, and client handoff guidance.
- [ ] Produce a connector capability matrix and acceptance report mapping every PRD Must requirement to pass, explicit deferral, or blocker.
- [ ] Rehearse the demo from a clean environment and record any manual step that prevents a repeatable client walkthrough.

## Canonical client demo

1. Open the seeded freight workspace and show the inbox row with priority and SLA state.
2. Open the conversation and show classification, rationale, `FT-204`/`TRK-204` extraction, evidence, summary, and route suggestion.
3. Claim or assign the conversation and show the activity event and second-client update.
4. Open the context rail and evidence-backed draft; show why send is unavailable before approval.
5. Edit the draft, approve the exact version, and demonstrate the separate send control.
6. Show SLA warning/breach and one escalation event.
7. Replay the inbound event and show no duplicate message or activity.
8. Attempt a stale edit from a second client, show `version_conflict`, reload, and recover.
9. Resolve the conversation and inspect event-derived analytics and audit history.

## Final acceptance gates

- [ ] The seeded demo works without live provider credentials.
- [ ] No unapproved or stale draft can be sent.
- [ ] Duplicate events, stale edits, retry failures, and low-confidence data are visible and recoverable.
- [ ] The UI follows the shared `design.md` schema and has explicit empty/error/degraded states.
- [ ] Tests prove workspace scoping, audit coverage, idempotency, collision protection, and SLA correctness.
- [ ] Every live integration claim is verified or labeled as fixture, blocked, or unknown.
- [ ] A client can start, reset, rehearse, and understand the prototype from the README and demo script.
