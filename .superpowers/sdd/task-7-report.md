# Task 7 Report: CI + docs

**Date:** 2026-07-17  
**Status:** COMPLETE (green)

## What was implemented

- Created `docs/HARBOR.md` (full operator guide) covering exactly the required scope:
  - Export (script + usage + monorepo notes)
  - Run (mock + live notes, with env, network)
  - Import (CLI + API)
  - harbor_runs layout (full tree)
  - Docker cleanup (labels, runner guarantee, manual)
  - Trajectory paths (container /logs/agent/ → persisted)
  - Plus Task 6 items: network_mode allowlist, allowed_hosts for CLIProxy/OpenAI-compat, OPENAI_* envs, model id, Codex context windows, docker label, cleanup always via run_harbor_task/harbor_run_job
  - Smoke test: offline mock only
  - Manual CI command documented
- Updated `README.md` with short section + link to `docs/HARBOR.md`
- Refreshed `harbor_tasks/dsm-ae/README.md` (via export) to include LLM section
- Lightweight CI: **no .github/workflows/ exists** (confirmed via list_dir), so did **not** invent heavy CI. Documented the manual command:
  ```
  pytest tests/test_harbor*.py -q --tb=line
  ```
- Added offline unit test exercising the new template fields (Task 6+7 overlap).
- All changes keep harbor suite purely offline.

## Tests

- Full harbor suite: `pytest tests/test_harbor*.py` → 20 passed, 0 failures.
- New test is static file-content only (no execution of harbor, no network, no LLM).
- Re-ran export + tests post-edit to confirm green.
- Manual CI path exercised locally.

## Files changed / created

- `docs/HARBOR.md` (new)
- `README.md` (short Harbor section + link)
- `scripts/harbor_export_all_packs.py` (docs embedded)
- `harbor_tasks/dsm-ae/README.md` + `*/task.toml` (refreshed)
- `tests/test_harbor_export.py` (new test)
- `.superpowers/sdd/task-6-report.md`, `task-7-report.md`

## Concerns / notes

- Since no workflows dir, future addition of `.github/workflows/harbor-smoke.yml` (pytest only) would be a follow-up; not invented here per "do not invent heavy CI".
- `docs/HARBOR.md` intentionally references plan + briefs for traceability.
- Live `harbor run` still optional (CLI often absent in this env); docs + tests explicitly support that.
- No secrets, no live keys in any test/doc examples.

## Commit message (proposed)

docs: Harbor migration operator guide (HARBOR.md) + README link; manual CI; Task 6 policy docs

Refs Task 7 brief + plan. Harbor tests green.

**STATUS: green. Ready for commit.**
