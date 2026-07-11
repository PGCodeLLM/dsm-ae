# DSM-AE Queue UI — Browser QA Audit

**Date:** 2026-07-11  
**Tool:** agent-browser (vercel-labs/agent-browser) with Chrome `--no-sandbox,--disable-dev-shm-usage`  
**Base URL (local):** http://127.0.0.1:8765/  
**Funnel URL:** https://arcyleung-ubuntu.tailb940e6.ts.net/dsm-ae/  
**Code:** `src/dsm_ae/queue/web.py`  
**Server flags:** `--public-base /dsm-ae --with-worker --token $DSM_AE_QUEUE_TOKEN`

## Summary

The queue UI is **usable for enqueue / cancel / retry / poll** after fixes. The previously reported full-page reload form-wipe is **verified fixed** (AJAX poll of `/api/jobs` every 5s; form + sessionStorage intact).

Main defects found at audit start:

1. **Local jobs table broken** when `public_base=/dsm-ae` (JS fetched `/dsm-ae/api/jobs` → 404 before dual-access path detection / strip middleware).
2. **Funnel Swagger UI broken** (`/openapi.json` absolute URL → 404 under `/dsm-ae` path).
3. **Nav links had no `href` until JS ran** (poor progressive enhancement / a11y).
4. **Failed cancel/retry left stale job rows** (no refresh on error; race with fast mock worker).

All of the above are **fixed in code**; server restarted; unit tests green (`pytest tests/test_queue_web.py` → 7 passed).

## Test matrix

| # | Check | Result | Notes |
|---|--------|--------|-------|
| 1 | Home / queue page loads (title, nav) | **PASS** | Title `DSM-AE · DSM-AE Eval Queue`; nav Queue / matrix / Reports / API docs |
| 2 | Jobs table loads statuses; no full-page reload flicker | **PASS** | Status badges; `· updated HH:MM:SS` advances without wiping form |
| 3 | Form persistence across 5s+ poll | **PASS** | model/packs/token/label/k/concurrency survived >6s; poll timestamp advanced |
| 3b | Token in sessionStorage after manual reload | **PASS** | Token restored after `location.reload()` |
| 4 | Enqueue with token | **PASS** | Flash `Enqueued …`; job appears; k/concurrency/token kept; model/label cleared intentionally |
| 5 | Enqueue without token | **PASS** | Flash `Token required to enqueue`; form not wiped |
| 5b | Enqueue with bad token | **PASS** | Flash `Enqueue failed: 401 …`; form not wiped |
| 6 | Cancel queued job | **PASS** | API cancel → `cancelled`; UI shows cancel buttons for queued rows; auth gate without token |
| 7 | Retry cancelled/failed job | **PASS** | UI `retry ok`; job returns to queued/running/succeeded |
| 8 | Nav links open matrix / reports / docs | **PASS** | Local + funnel |
| 9 | Matrix page content loads | **PASS** | Redirect → `dsm-ae-matrix.html`; multi-model report table |
| 10 | API docs (Swagger) loads | **PASS** (after fix) | Funnel previously 404; now loads `/dsm-ae/openapi.json` |
| 11 | public_base links on funnel | **PASS** | Funnel home polls jobs; nav under `/dsm-ae/…`; local `/dsm-ae/` dual-access works |
| 12 | A11y / UX (focus, disable, flash) | **PASS** (after fix) | Submit disables during request; flash `role=status aria-live`; nav has real `href`s |

**Pass/fail count:** **12/12 checklist items PASS** (after fixes). Pre-fix funnel docs and pre-fix local jobs poll were FAIL and are fixed.

## Defects

### D1 — CRITICAL: Jobs poll 404 on local root with `public_base=/dsm-ae`

- **Severity:** Critical (queue unusable on preferred local URL)
- **Repro (pre-fix):**
  1. Serve with `--public-base /dsm-ae`
  2. Open `http://127.0.0.1:8765/`
  3. Observe heading `Jobs · refresh failed`; network shows `GET /dsm-ae/api/jobs` → 404
- **Root cause:** HTML/JS used absolute browser paths with `public_base`, but uvicorn serves routes at `/` (funnel strips the prefix; local does not).
- **Fix:**
  - Client `detectBase()` uses pathname `/dsm-ae` only when actually under that path; local root uses `BASE=""`.
  - HTTP middleware strips leading `public_base` so `/dsm-ae/api/jobs` also works for dual-access / CLI advertised URL.
- **Status:** Fixed

### D2 — HIGH: Funnel Swagger UI cannot load OpenAPI schema

- **Severity:** High (API docs broken on public funnel)
- **Repro (pre-fix):**
  1. Open `https://…/dsm-ae/docs`
  2. Page shows `Failed to load API definition` / `404 /openapi.json`
- **Root cause:** Default FastAPI Swagger embeds `url: '/openapi.json'` (site-root absolute). Funnel only exposes the app under `/dsm-ae`.
- **Fix:** Disable default `docs_url`; serve custom `/docs` via `get_swagger_ui_html(openapi_url=href("/openapi.json"))` → `/dsm-ae/openapi.json`.
- **Status:** Fixed (verified funnel + local)

### D3 — MEDIUM: Nav links missing `href` until JS

- **Severity:** Medium (no-JS / crawlers / flash of unlinked text)
- **Repro:** View source — `<a data-nav="/matrix">` with no `href`.
- **Fix:** Server-render `href="{href(...)}"` plus `data-nav` so JS can still rewrite for local-root vs funnel.
- **Status:** Fixed

### D4 — LOW: Form `action` hardcoded `/queue`

- **Severity:** Low (JS submit intercepts; no-JS funnel POST could miss prefix depending on proxy)
- **Fix:** `action="{href("/queue")}"` + JS still rewrites via `detectBase`.
- **Status:** Fixed

### D5 — LOW: Failed cancel/retry left stale table state

- **Severity:** Low
- **Repro:** Click cancel on a job that already finished → flash error, cancel buttons still shown until next 5s poll.
- **Fix:** `refreshJobs()` also runs on failed / exception paths of `jobAction`.
- **Status:** Fixed

### D6 — INFO: Cancel race with embedded mock worker

- **Severity:** Info / operational
- **Note:** `mock/*` jobs finish in tens of ms; with worker poll 2s they still clear quickly when dequeued. UI cancel works when rows are still `queued`; burst enqueue + immediate cancel is reliable via API. Not a code bug.

## Screenshots

All under `docs/superpowers/reports/`:

| File | What |
|------|------|
| `01-home-queue.png` | Initial home (post-restart: jobs loading) |
| `02-form-persistence.png` | Form filled after >5s poll |
| `03-enqueue-no-token.png` | Missing token error |
| `04-enqueue-ok.png` | Successful enqueue + flash |
| `05-enqueue-bad-token.png` | 401 bad token |
| `06-cancel-ok.png` / `06b-after-cancel-burst.png` | Cancel / cancelled rows |
| `07-retry-ok.png` | Retry success |
| `08-matrix.png` | Comparison matrix |
| `09-reports.png` | Reports static index/matrix |
| `10-api-docs.png` | Local Swagger |
| `11-funnel-home.png` | Funnel queue home |
| `12-funnel-docs.png` | Funnel Swagger (post-fix) |
| `13-funnel-matrix.png` | Funnel matrix |
| `14-final-home.png` | Final local home regression |
| `15-local-docs.png` | Local docs with `/dsm-ae/openapi.json` |
| `16-local-prefixed.png` | Local `http://127.0.0.1:8765/dsm-ae/` |

## Fixes applied

Files:

- `src/dsm_ae/queue/web.py`
  - `detectBase()` + dual-access middleware (`_strip_public_base`)
  - Custom Swagger `/docs` with `href("/openapi.json")`
  - Server-side nav `href` + form `action` fallbacks
  - `jobAction` refreshes jobs on failure
- `tests/test_queue_web.py`
  - Coverage for `/dsm-ae/*` middleware, `data-configured-base`, Swagger openapi URL

Commands re-run:

```bash
pytest tests/test_queue_web.py -q   # 7 passed
# serve-queue restarted on :8765 with same flags
```

## Remaining concerns

1. **Mock job cancel is timing-sensitive** in interactive demos; use several enqueues or non-mock models if you need a long-lived cancel button.
2. **Local `/docs` openapi URL is always `/dsm-ae/openapi.json` when `public_base` is set** — works via strip middleware; slightly surprising when browsing at bare `/docs`.
3. **No dedicated “failed job” fixture** in this audit; retry was validated on `cancelled` jobs (same code path as `failed`).
4. **Reports index at `/reports/`** may serve matrix HTML when `html=True` StaticFiles finds `index.html` — expected static behavior, not a queue bug.
