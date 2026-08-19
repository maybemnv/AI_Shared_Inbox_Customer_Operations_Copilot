# Client demo script

## Preflight

1. Confirm Python and Node are installed.
2. From the repository root, create the validation environment and install the
   development contract:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements-dev.txt
   python -B -m pytest -p no:cacheprovider -q
   python -m ruff check --no-cache app tests
   ```

3. Start the API:

   ```powershell
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8103
   ```

4. In a second terminal, install and start the workbench:

   ```powershell
   Set-Location apps/web
   npm ci
   npm run build
   $env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8103"
   npm run dev -- --hostname 127.0.0.1 --port 3103
   ```

4. Open `http://127.0.0.1:3103/inbox`. The header must say `Fixture mode · live unconfigured`.

5. Check the API and reset the fixture before opening
   `http://127.0.0.1:3103/inbox`:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8103/healthz
   Invoke-RestMethod http://127.0.0.1:8103/readyz
   Invoke-RestMethod http://127.0.0.1:8103/api/v1/demo/reset -Method Post
   ```

## Walkthrough

1. In Queue, open the single Jordan Lee conversation. Point out `FT-204`, the high priority, Gmail fixture source, queue, owner, and version.
2. Select `Run safe draft`. Show the classification rationale, `TRK-204` tracking context, known facts, and missing account/delivery-date evidence.
3. Select `Claim`, then `Start SLA`. The activity list records both operator/system decisions and the version advances.
4. In Response draft, edit the body and save. Explain that saving returns the draft to `approval_required`.
5. Select `Approve vN`, then separately select `Send approved`. The response says `fixture_only`; no provider was contacted.
6. For the SLA path, call the evaluation endpoint with `2026-08-09T01:05:00+00:00` or use the API request below. Show `breached` and the single `fixture_only` escalation.
7. Replay the inbound event with the sync endpoint. The cursor advances/returns and the duplicate count is visible without adding a second message.
8. Resolve the conversation and show the `resolved` state and audit activity.

## Safe API rehearsal

```powershell
  Invoke-RestMethod http://127.0.0.1:8103/api/v1/connectors/fixture-gmail/sync `
  -Method Post -ContentType 'application/json' `
  -Body '{"kind":"inbound","idempotency_key":"demo-replay-1"}'

Invoke-RestMethod http://127.0.0.1:8103/api/v1/conversations/conversation-ft-204/sla/evaluate `
  -Method Post -ContentType 'application/json' `
  -Body '{"now":"2026-08-09T01:05:00+00:00"}'
```

## Reset and fallback

- Run `Invoke-RestMethod http://127.0.0.1:8103/api/v1/demo/reset -Method Post`
  to reset the in-memory fixture without restarting the process, then refresh
  the browser.
- Stop both local processes with `Ctrl+C`; no durable data is changed.
- If the web API is unavailable, use `/healthz`, `/readyz`, and the API commands directly; do not present the UI as live.
- If a command returns `version_conflict`, reload the conversation and use the current displayed version. Never retry a send with a new idempotency key after an ambiguous provider error.
