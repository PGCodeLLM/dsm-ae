# Task 4 Report: Multi-step / k-trial mapping

**Status:** DONE  
**Date:** 2026-07-17

---

## What was done

### 1. Documented the mapping (default = outer loop)

- Updated `scripts/harbor_export_all_packs.py` `_build_task_toml` with detailed docstring explaining:
  - k-trials = outer loop (Harbor task = 1 trial; driver loops k times)
  - Multi-step `[[steps]]` only for ordered phases inside one trial
- Updated `harbor_tasks/dsm-ae/tool_integrity_tier2/task.toml` (and generator) with:
  ```toml
  gold_read_fault = "..."
  notes = "k-trials via outer loop; fault injection inside run_trial..."
  ```
- Extended `harbor_tasks/dsm-ae/tool_integrity_tier2/README.md` and `harbor_tasks/dsm-ae/README.md` with full Task 4 section describing:
  - Outer loop rationale
  - GoldReadFault handling (via adapter inside pack, not steps)
  - When to use `[[steps]]`
  - Cross refs to briefs/plan/runner

### 2. Added `scripts/harbor_run_job.py`

- CLI + lib `run_harbor_job(job_id, model, packs, k=...)`
- For each `pack × trial`:
  - `_mock_task_fn` calls `prepare_workspace` + `score_workspace` (bridge)
  - Returns harbor reward dict (floats) → runner auto-persists to `rewards/{pack}__t{i}.json`
  - `score_workspace` (mock) already writes `trajectories/{pack}__t{i}/*` (scores, meta, etc.)
- Always uses `run_harbor_task(...)` wrapper → guaranteed `cleanup_docker_for_job(job_id)` (in finally) + `docker_cleanup.json`
- Labels documented: `dsm-ae.harbor.job={job_id}` (for real harbor/docker invocations inside a task_fn)
- Fully offline: `model=mock/*` path never requires harbor CLI or containers (uses `MockClient` via bridge)
- Updates `meta.json` with `k_trials`
- Works for multiple packs + k>1 in single job dir under `reports/harbor_runs/{job_id}` (or `--base` override)

### 3. Tests

- New: `tests/test_harbor_run_job.py`
  - `test_harbor_run_job_offline_creates_artifacts_and_calls_cleanup`
  - `test_harbor_run_job_cli_smoke`
- All use monkeypatched cleanup; assert rewards + traj layout + meta + cleanup calls
- `pytest ... -q` green (no live harbor)

### 4. Integration

- `harbor_run_job` re-uses existing `pack_bridge`, `run_layout`, `runner`
- Compatible with already-exported `harbor_tasks/dsm-ae/*`
- For tool_integrity_tier2 the internal hard arm (fault + recovery) is exercised inside the mock `run_trial` called by bridge during scoring

---

## Files changed

| Path | Change |
|------|--------|
| `scripts/harbor_export_all_packs.py` | docstring + special metadata for tier2 in toml builder |
| `harbor_tasks/dsm-ae/tool_integrity_tier2/task.toml` | added gold_read_fault + notes |
| `harbor_tasks/dsm-ae/tool_integrity_tier2/README.md` | full Task 4 mapping + GoldReadFault explanation |
| `harbor_tasks/dsm-ae/README.md` | new section "Task 4: Multi-step / k-trial mapping..." |
| `scripts/harbor_run_job.py` | **Created** (executable) |
| `tests/test_harbor_run_job.py` | **Created** |
| `src/dsm_ae/harbor/__init__.py` | (minor) doc update |

---

## Verification

| Check | Result |
|-------|--------|
| `python -m py_compile scripts/harbor_run_job.py` | OK |
| `pytest tests/test_harbor_run_job.py tests/test_harbor*.py -q` | 19 passed |
| Manual: `python scripts/harbor_run_job.py --job-id X --model mock/... --packs hello_metacog,tool_integrity_tier2 --k 2 --base /tmp/t` | produces rewards/*__t*.json + trajectories + docker_cleanup.json |
| `python -c 'from dsm_ae.harbor import run_harbor_task; ...'` | no breakage |
| No `harbor` binary used or required | confirmed (offline) |

---

## Self-review

- Matches brief + plan: outer loop default, only doc for tier2 fault (no [[steps]] added as "if heavy"), `harbor_run_job.py` takes job/model/packs/k , ensures artifacts, labels doc'd, always cleanup via runner, mock task_fn using pack_bridge.
- Concerns: none blocking. For live harbor path the caller will supply task_fn that execs `harbor run ...` with the label (runner still wraps for cleanup + layout).
- K-trials are independent (different persona/seed via mock or real); matches DSM-AE ScaffoldCard.k_trials.

---

## STATUS for Task 4

**GREEN** — implemented, tested, docs written.
