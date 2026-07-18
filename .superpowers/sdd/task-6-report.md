# Task 6 Report: LLM agent path + network policy

**Date:** 2026-07-17  
**Status:** COMPLETE (green)

## What was implemented

- Updated `scripts/harbor_export_all_packs.py` `_build_task_toml` (and embedded docs) to include `[agent]` section metadata template fields distinguishing LLM profile vs smoke:
  - `network_mode = "allowlist"` guidance + `allowed_hosts` example for proxy/OpenAI-compat.
  - Env var docs: `OPENAI_API_BASE`, `OPENAI_API_KEY`, model id (via `-m`).
  - Context windows: explicit note to use operational Codex values (272k for gpt-5.5, 372k for 5.6 family) **not** marketing 1.05M.
  - All 22 generated `harbor_tasks/dsm-ae/*/task.toml` refreshed (via re-export); `_template/` updated.
- Added comprehensive documentation to:
  - `harbor_tasks/dsm-ae/README.md` (top level, refreshed by export) — LLM network policy section.
  - `docs/HARBOR.md` (created in tandem with Task 7) — full coverage of allowlist, allowed_hosts, envs, windows, docker label `dsm-ae.harbor.job={job_id}`, always-cleanup via `run_harbor_task` / `harbor_run_job`.
- Smoke test path remains **offline only (mock)**: `harbor_run_job.py --model mock/*` + `pack_bridge` (MockClient) + existing tests. No live LLM calls or keys exercised.
- Verified no code changes required live agents (Harbor `-a` agent provides the execution; DSM-AE bridge only for scoring/verifier; `RawToolLoopAdapter` paths used only in mock scoring).
- Added one new offline unit test in `tests/test_harbor_export.py::test_export_includes_llm_network_policy_and_context_notes` (asserts static fields in generated toml).

## Tests

- `pytest tests/test_harbor*.py -q` → **20 passed** (all green, including new test + prior bridge/run_layout/import/export).
- No new live dependencies; export + mock scoring only.
- Re-export validated determinism of templates.

## Files changed / created

- `scripts/harbor_export_all_packs.py` (template + docstrings + README content)
- `harbor_tasks/dsm-ae/*/*/task.toml` (22 refreshed)
- `harbor_tasks/dsm-ae/README.md` (refreshed)
- `tests/test_harbor_export.py` (new test)
- `docs/HARBOR.md` (covers Task 6 items)
- `README.md` (link section)

## Concerns / notes

- Harbor's exact support for `network_mode` / `allowed_hosts` under `[agent]` vs `[environment]` may vary by version; documented as guidance + comments (users override per their Harbor).
- Actual agent execution inside container (for live) is out-of-scope of DSM-AE (provided by harbor agent impl); we only document env + net policy to reach proxy.
- Context window rule is advisory for users building bloat/history stuffing agents; DSM-AE bloat code already prefers the Codex values.
- Docker label + runner cleanup already implemented in prior tasks; just documented here as required.

## Commit message (proposed)

docs(harbor): LLM agent network policy, allowed_hosts, env vars, Codex windows (272k/372k), labels, always-cleanup

Refs Task 6 brief + plan global constraints.

**All harbor tests green. Smoke offline only.**
