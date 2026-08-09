# Client demo acceptance contract

This checklist maps the PRD's canonical traces to the verified local fixture
path. It deliberately distinguishes `pass`, `fixture-only`, and `open`.

## Trace 1 — freight delay

- [x] `fixtures/freight_delay.json` seeds Jordan Lee, `FT-204`, and the Gmail source envelope.
- [x] Identity normalization creates one conversation/message and replay is safe (`tests/test_ingestion.py`).
- [x] Classification exposes typed request type, priority, confidence, rationale, and message evidence (`tests/test_operations.py`).
- [x] Ordered routing assigns `freight-operations` / `operator-freight` with a reason.
- [x] Fixture extraction keeps account and promised date nullable and exposes `TRK-204` tracking evidence.
- [x] Summary and draft show known/missing facts; the draft does not promise an unverified date.
- [x] Edit, exact-version approval, and separate send are API commands; send is `fixture_only` (`tests/test_drafting.py`).
- [x] SLA start, warning, breach, one `fixture_only` escalation, and resolve are deterministic (`tests/test_phase4.py`).
- [ ] Supabase persistence, realtime delivery, live provider send, and a real escalation connector remain open.

## Trace 2 — duplicate and collision recovery

- [x] Duplicate provider event/message creates no second message or activity.
- [x] Two concurrent assignments yield one versioned winner and one `version_conflict`.
- [x] Stale draft edits and stale approvals cannot overwrite or send.
- [ ] Two browser clients receiving realtime updates and reconnect replay remain open.

## Trace 3 — low confidence / missing match

- [x] Unknown request type remains `unknown` with bounded low confidence.
- [x] Unknown work routes to `queue-unassigned` with a visible fallback reason.
- [x] Missing account/shipment fields remain null; no unrelated record is guessed.
- [ ] Operator account-link flow remains open in the UI.

## Release evidence

- Backend: `python -m pytest -p no:cacheprovider -q` — verified locally; latest run is recorded in the handoff message.
- Lint: `python -m ruff check --no-cache app tests` — verified locally.
- Web: `npm run build` in `apps/web` — verified locally on Next.js 16.3.0.
- Dependency audit: `npm audit --audit-level=high` — verified with zero vulnerabilities after the Next.js upgrade.
- Live readiness: not verified; no Supabase URL, auth, provider OAuth, queue, realtime, or external connector secret is present.
