# Plan 001: Make the shared inbox fixture demo repeatable and browser-verified

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report; do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer dispatched you and told you they maintain
> the index.
>
> **Drift check (run first)**: `git diff --stat 1d9ab77..HEAD -- app/main.py app/ingestion.py app/fixture.py requirements.txt tests apps/web README.md deployment.md DEMO_SCRIPT.md RUNBOOK.md`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: none
- **Category**: dx, tests, docs, direction
- **Planned at**: commit `1d9ab77`, 2026-08-19
- **Issue**: omit unless published explicitly by the operator

## Why this matters

The repository already has a deterministic freight-delay fixture, a working
FastAPI command surface, and a passing Next.js production build, but the
showcase cannot be reset by an explicit API command and has no browser smoke
gate. The documented preflight also invokes Ruff even though Ruff is not part
of the install contract. This plan makes the existing fixture path repeatable
on ports API `8103` and web `3103`, verifies the desktop/mobile operator story,
and makes unfinished secondary navigation honest without expanding into a
durable Supabase implementation.

## Current state

- `app/main.py` — FastAPI application and fixture endpoints. `create_app()`
  captures an optional test repository, otherwise returning the process-global
  `demo_inbox` (`app/main.py:119-125`). The app exposes `/healthz` and `/readyz`
  (`app/main.py:222-237`) but no reset endpoint.
- `app/ingestion.py` — in-memory fixture repository with locking and identity
  checks. Its constructor owns events, conversations, drafts, sync jobs,
  connector state, and escalation state (`app/ingestion.py:76-105`).
- `app/fixture.py` — loads `fixtures/freight_delay.json` and seeds one inbox
  (`app/fixture.py:8-20`).
- `requirements.txt` — pins FastAPI, HTTPX, pytest, and Uvicorn, but does not
  install Ruff (`requirements.txt:1-4`).
- `tests/` — API, ingestion, drafting, operations, and acceptance tests. The
  verified local backend command was `python -B -m pytest -p no:cacheprovider -q`
  with 31 passing tests at the planned SHA.
- `apps/web/components/InboxWorkbench.tsx` — primary browser workbench and
  navigation. It advertises Inbox, Customers, Rules, Analytics, and
  Integrations (`apps/web/components/InboxWorkbench.tsx:18-24`).
- `apps/web/app/analytics/page.tsx`, `apps/web/app/rules/page.tsx`,
  `apps/web/app/customers/[customerId]/page.tsx`, and
  `apps/web/app/settings/integrations/page.tsx` — currently all return the
  same `InboxWorkbench` component; for example Analytics is only
  `return <InboxWorkbench />` (`apps/web/app/analytics/page.tsx:1-5`).
- `apps/web/package.json` — has only `dev`, `build`, and `start` scripts
  (`apps/web/package.json:5-9`); no browser-test command exists.
- `deployment.md` — starts API and web on default ports 8000 and 3000 and
  instructs `python -m ruff check --no-cache app tests` (`deployment.md:37-58,
  101-108`). This plan changes the documented showcase ports to API 8103 and
  web 3103 while retaining configurable overrides only if they are explicitly
  documented.

The showcase contract requires a documented setup, reset, start, health
check, desktop/mobile browser smoke path, and explicit fixture/live boundary.
The current fixture remains the only default adapter; do not implement
Supabase, authentication, queues, realtime, or live provider behavior here.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Backend tests | `python -B -m pytest -p no:cacheprovider -q` | exit 0; all existing and new tests pass |
| Ruff | `python -m ruff check --no-cache app tests` | exit 0 with no diagnostics |
| Web dependencies | `npm ci` from `apps/web` | exit 0 using the committed lockfile |
| Web build | `npm run build` from `apps/web` | exit 0; Next.js production build succeeds |
| API start | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8103` | process listens on 8103 |
| Web start | `npm run dev -- --hostname 127.0.0.1 --port 3103` from `apps/web` | process serves the workbench on 3103 |
| API health | `Invoke-RestMethod http://127.0.0.1:8103/healthz` | process health is `ok` and mode is `fixture` |
| API readiness | `Invoke-RestMethod http://127.0.0.1:8103/readyz` | fixture dependencies are reported honestly and seed is present |
| Browser smoke | `npm run test:e2e` from `apps/web` | desktop and mobile specs pass |

Do not run install commands until the executor is in the implementation branch
and the operator has authorized dependency installation. Read-only planning
does not authorize network access.

## Suggested executor toolkit

- Use the existing Python `pytest` and FastAPI `TestClient` patterns in
  `tests/test_api.py` and `tests/test_acceptance.py`.
- Use Playwright for the browser smoke test. The test must start the API on
  8103 and Next.js on 3103, or use an explicitly documented equivalent that
  does not rely on a manually running process.
- Invoke `superpowers:test-driven-development` before behavior changes and
  `superpowers:verification-before-completion` before making completion claims.
- Follow the repository's existing TypeScript and CSS conventions. Do not
  introduce a component library or a new backend framework.

## Scope

**In scope** (the only files this plan may modify):

- `app/main.py`
- `app/ingestion.py`
- `app/fixture.py`
- `requirements.txt` or one new `requirements-dev.txt` if the executor can
  keep runtime installation separate and documents both commands
- `tests/test_api.py`
- `tests/test_acceptance.py`
- `tests/test_demo_reset.py` (create if keeping reset tests separate)
- `apps/web/package.json`
- `apps/web/package-lock.json`
- `apps/web/playwright.config.ts` (create)
- `apps/web/e2e/inbox-demo.spec.ts` (create)
- `apps/web/components/InboxWorkbench.tsx`
- `apps/web/app/analytics/page.tsx`
- `apps/web/app/rules/page.tsx`
- `apps/web/app/customers/[customerId]/page.tsx`
- `apps/web/app/settings/integrations/page.tsx`
- `README.md`
- `deployment.md`
- `DEMO_SCRIPT.md`
- `RUNBOOK.md`
- `plans/README.md` and this plan file

**Out of scope** (do NOT touch, even though they look related):

- `db/migrations/001_initial.sql` and `db/seed_freight_demo.sql` — prepared
  durable artifacts are not part of the fixture showcase change.
- `PRD.md` and `tasks.md` — preserve the product source documents; reconcile
  only the operational README/deployment/demo docs in this plan.
- Any Supabase, authentication, authorization, queue, realtime, live AI, or
  provider connector implementation.
- Any root workspace file or another product repository.

## Git workflow

- Branch: `feat/demo-showcase-ready` from the planned SHA.
- Keep the plan artifacts in the repository; source changes must stay within
  the scope list above.
- Commit checkpoint 1 after reset/readiness tests and implementation.
- Commit checkpoint 2 after tooling/docs changes.
- Commit checkpoint 3 after browser smoke and navigation honesty changes.
- Use the repository's existing concise commit style; include the verification
  command in the handoff message.
- Do not push, open a PR, or merge unless the operator separately authorizes
  publishing. A local branch and local commits are sufficient for this plan.

## Steps

### Step 1: Add a repeat-safe fixture reset and data-aware readiness contract

1. Add an `InMemoryInbox` reset operation that clears all mutable fixture
   maps/lists under the existing `RLock`, then ingests the canonical event from
   `build_freight_delay_event()`. Preserve the optional repository injection
   used by tests; do not create a second global repository.
2. Add a fixture-only reset route under `/api/v1/demo/reset`. It must return
   the mode, workspace, and seeded conversation identifier. Make repeated calls
   idempotent and do not add a reset path for a future durable backend.
3. Make `/readyz` confirm that the expected seeded conversation is present,
   while retaining explicit `database`, `queue`, `realtime`, and `provider`
   boundary labels. A process-health check must not be represented as durable
   readiness.
4. Add API tests for reset twice, seeded conversation/version baseline, and
   reset isolation through the existing workspace query patterns.

**Red verification**: Before implementation, add the tests and run
`python -B -m pytest -p no:cacheprovider tests/test_demo_reset.py tests/test_api.py -q`.
The new reset tests must fail because no reset route/method exists yet.

**Green verification**: Implement the smallest reset/readiness change, then run
`python -B -m pytest -p no:cacheprovider tests/test_demo_reset.py tests/test_api.py -q`.
Expected result: all selected tests pass, including reset idempotence.

**Checkpoint**: Run `python -B -m pytest -p no:cacheprovider -q`; expected
result is all tests passing. Commit checkpoint 1 only after this gate.

### Step 2: Make clean setup and documented ports reproducible

1. Add a pinned Ruff development dependency without moving production code or
   introducing a second untracked package manager. If using
   `requirements-dev.txt`, make it install `-r requirements.txt` and Ruff, and
   update every setup command to install the dev file for showcase validation.
2. Update `deployment.md`, `README.md`, `RUNBOOK.md`, and `DEMO_SCRIPT.md` to
   use API port 8103 and web port 3103, with exact PowerShell commands for
   prerequisites, virtualenv setup, `npm ci`, backend tests, Ruff, web build,
   API start, web start, health/readiness, reset, and shutdown.
3. State that all integrations are fixture-only, paid credentials are not
   required, and the reset affects only the in-memory fixture.

**Red verification**: On a clean virtualenv before adding the dependency,
`python -m ruff check --no-cache app tests` must fail with the missing-tool
condition observed at the planned SHA. Do not preserve this failure after the
step.

**Green verification**: Run `python -m ruff check --no-cache app tests` and
`python -B -m pytest -p no:cacheprovider -q`; expected result is exit 0 for both.
From `apps/web`, run `npm ci` and `npm run build`; expected result is exit 0.

**Checkpoint**: Commit checkpoint 2 after the clean-tooling and port docs are
verified. Do not push or open a PR without operator authorization.

### Step 3: Add the browser smoke test for the primary story

1. Add the minimum Playwright test dependency and lockfile update. Add a
   `playwright.config.ts` that starts the API on 8103 and web on 3103, or
   explicitly documents a safe equivalent. Do not add a live provider or a
   second backend.
2. Add `apps/web/e2e/inbox-demo.spec.ts`. Before each test, call the reset
   endpoint. At desktop width, assert the seeded Jordan Lee/freight-delay
   conversation, run safe draft, claim, start SLA, edit the draft, save, exact
   version approval, and separate fixture-only send. Assert that the visible
   UI identifies the connector as fixture and does not claim live delivery.
3. At a 390px-wide viewport, assert the page remains usable and the critical
   controls are visible or reachable without horizontal overflow. Include one
   API-error case and verify a visible error state does not enable later send
   actions.
4. Add `test:e2e` to `apps/web/package.json` and document its command and
   browser prerequisite in the runbook.

**Red verification**: Run `npm run test:e2e` before the browser implementation
is complete. It must fail because the script/spec is not yet present or because
the primary flow assertions are unmet.

**Green verification**: Start through the Playwright web-server configuration
and run `npm run test:e2e`; expected result is all desktop and mobile specs pass.
Then rerun `npm run build` to ensure the test additions do not affect the
production build.

### Step 4: Make secondary navigation honest

1. Keep `/inbox` as the only completed primary route.
2. Either remove unfinished secondary links from `navItems` or render explicit
   fixture-planned placeholders with clear “planned/not implemented” wording.
   Do not leave Analytics, Rules, Customers, or Integrations pointing at an
   indistinguishable inbox workbench.
3. Update the browser smoke test to assert the chosen honest behavior and keep
   the docs aligned with the actual route surface.

**Verify**: `npm run build` from `apps/web` exits 0, and
`npm run test:e2e` confirms no secondary link falsely presents an unrelated
completed workflow.

### Step 5: Final showcase verification

Run, in this order:

1. `python -m ruff check --no-cache app tests` → exit 0.
2. `python -B -m pytest -p no:cacheprovider -q` → all tests pass.
3. `npm ci` and `npm run build` from `apps/web` → exit 0.
4. Start API on 8103 and web on 3103.
5. `Invoke-RestMethod http://127.0.0.1:8103/healthz` and `/readyz` → process and fixture readiness are explicit.
6. Run `npm run test:e2e` → desktop/mobile primary flow passes.
7. `git status --short` → only intended source/docs/plan files are changed.

## Test plan

- Reset/readiness tests: model API style from `tests/test_api.py` and fixture
  construction from `tests/test_acceptance.py`; cover reset twice, seeded
  version baseline, and fixture-only readiness.
- Browser tests: add the primary flow and mobile-width assertions described in
  Step 3; cover an API rejection so the UI cannot show false success.
- Existing regression suite: retain all 31 current tests and the existing
  concurrency, stale-write, approval, replay, SLA, and workspace-scope tests.
- Tooling gate: Ruff and Next.js build must remain green.

## Done criteria

- [ ] `POST http://127.0.0.1:8103/api/v1/demo/reset` is documented and safe to repeat.
- [ ] `/healthz` and `/readyz` distinguish process health from seeded fixture readiness.
- [ ] `python -m ruff check --no-cache app tests` exits 0 from the documented environment.
- [ ] `python -B -m pytest -p no:cacheprovider -q` exits 0 with all existing/new tests passing.
- [ ] `npm ci` and `npm run build` from `apps/web` exit 0.
- [ ] `npm run test:e2e` covers the desktop primary flow and 390px mobile layout.
- [ ] The browser proves draft → claim/SLA → edit → exact approval → fixture-only send.
- [ ] Secondary navigation does not imply unfinished routes are complete.
- [ ] README, deployment, demo script, and runbook use API 8103/web 3103 and include setup, health, reset, and shutdown.
- [ ] `git status --short` contains no files outside Scope.
- [ ] No push, PR, or merge occurred without explicit authorization.

## STOP conditions

Stop and report back if:

- The code at any Current state location differs materially from the excerpts.
- Resetting the repository would require touching `db/`, Supabase, or another
  out-of-scope product.
- The selected browser runner cannot start API 8103 and web 3103 without a
  provider credential or an undocumented manual process.
- The reset operation could affect a durable backend or data outside the
  fixture/demo workspace.
- A verification command fails twice after a reasonable correction attempt.
- Adding Playwright requires broad frontend restructuring rather than a small
  test-only dependency/configuration change.
- Any requested change would require reproducing a credential, token, or
  `.env` value; record only its file/line and credential type, then stop.

## Maintenance notes

- Keep the reset implementation fixture-only until a separately reviewed
  durable repository exists.
- If the fixture event shape or conversation version changes, update the reset
  tests and browser assertions together.
- Reviewers should scrutinize exact-version approval, fixture-only send labels,
  reset isolation, and whether mobile assertions test usable controls rather
  than only page presence.
- Analytics, realtime, Supabase, authentication, and live connector behavior
  remain explicitly deferred; unfinished navigation should not imply otherwise.
