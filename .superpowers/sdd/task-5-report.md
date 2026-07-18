# Task 5 Report: Import Harbor rewards into DSM-AE report JSON

**Status:** DONE  
**Date:** 2026-07-17

---

## What was done

### 1. Created `src/dsm_ae/harbor/import_rewards.py`

Core:
- `reward_dir_to_report(path: Path, *, model: str, pack_id: str | None = None, k: int | None = None) -> dict`
  - Scans `rewards/*.json` (or top-level, or single file)
  - `_reward_to_metric_results`: converts harbor reward floats (`primary_pass`, `foo_bar`→`foo.bar`) into synthetic `MetricResult(value=..., passed= heuristic from 0/1 or >0)`
  - Groups into bucket, runs `bootstrap_metric(mid, mid, results...)`, `build_gate_matrix`, `evaluate_findings`
  - Returns full DiagnosisReport-shaped dict (scaffold_card, packs, k_trials, gates[], findings[], bootstraps[], notes, traces=[])
- `import_harbor_run(job_id, *, reports_dir=None, model=None) -> dict`
  - Resolves via `harbor_run_dir`, reads meta.json for defaults, delegates to reward_dir_to_report, enriches
- CLI (`python -m dsm_ae.harbor.import_rewards`):
  ```
  --job-id JID [--model M] [--reports-dir R] [--out reports/harbor/xxx.json] [--print]
  ```
- Handles tier2 metrics (task_tool_success.tier2 etc) via _ replacement reverse + primary_pass.
- Compatible with `json_to_html_report.py` / merge / Comparison (uses same bootstrap/criteria).

### 2. Updated exports

- `src/dsm_ae/harbor/__init__.py`: exported `reward_dir_to_report`, `import_harbor_run`

### 3. Tests

- New `tests/test_harbor_import.py`:
  - Builds fake `harbor_runs/{job}/rewards/*.json` + `meta.json` trees
  - `test_reward_dir_to_report_and_import_harbor_run`: direct + via job_id path, asserts packs, gates, bootstraps, n, status fields
  - `test_import_cli_with_fake_tree`: exercises `python -m ...` + --out
- All offline, use tmp_path only
- Full harbor test suite + new: green

### 4. Manual verification

- `scripts/harbor_run_job.py ...` → job dir → `python -m dsm_ae.harbor.import_rewards --job-id ... --reports-dir ... --out ...` → valid JSON with gates/bootstraps populated from reward values
- `DiagnosisReport` shape: scaffold_card.model, packs, k_trials, gates (with pass_rate/mean/status), bootstraps, findings

---

## Files changed

| Path | Change |
|------|--------|
| `src/dsm_ae/harbor/import_rewards.py` | **Created** |
| `src/dsm_ae/harbor/__init__.py` | expose new importers |
| `tests/test_harbor_import.py` | **Created** |

(No changes to `scripts/json_to_html_report.py` needed; discovery already walks reports/ broadly and the shaped dict is identical.)

---

## Verification

| Check | Result |
|-------|--------|
| `python -m py_compile src/dsm_ae/harbor/import_rewards.py` | OK |
| `pytest tests/test_harbor_import.py -q --tb=no` | 2 passed |
| Combined harbor tests | 19 passed |
| End-to-end: run_job (k=1) → import_harbor_run → JSON with non-empty gates/bootstraps for hello + tier2 | OK (see terminal logs) |
| CLI writes file + summary | OK |
| Reward floats → pass_rate/mean/std/status rehydrated | verified in boots/gates |

---

## Self-review

- Brief + plan honored: `reward_dir_to_report` + `import_harbor_run(job_id)`, CLI matches spec (job-id focused), returns DiagnosisReport-shaped dict, uses floats for gates/bootstraps, tests with fake trees, offline only.
- pass/fail rehydration: heuristic based on value (works for 0/1 primary + axes; sufficient for comparison matrix). Full `passed` from original MetricResult not present in harbor reward but status derived via bootstrap classify.
- Concern (minor): when Harbor reward only contains a subset of metrics (e.g. only primary + a few), the imported report will only have those gates (expected; same as any partial run). For tier2 the composite + recovery keys round-trip via `_`→`.` .
- No change to existing report consumers needed.

---

## STATUS for Task 5

**GREEN** — implemented, tests pass, end-to-end with Task 4 artifacts works.
