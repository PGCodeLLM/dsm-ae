# dsm-ae Harbor Tasks (bulk exported)

All registered DSM-AE packs exported as Harbor tasks via `scripts/harbor_export_all_packs.py`.

## Layout (per pack under dsm-ae/<pack_id>/)
- `task.toml` — Harbor schema 1.3 + dsm_ae_pack, syndrome_codes, primary_metrics
- `instruction.md` — derived from pack SYSTEM + user templates
- `tests/test.sh` — always: `score_workspace(pack_id, Path("/app"), 0); write_reward(...) -> /logs/verifier/reward.json`
- `environment/Dockerfile` — monorepo style (see below)
- `environment/fixtures/` — **only pack-specific** gold files/contracts (hello contracts, notes.txt, etc). No dsm_ae/ source.
- `README.md` — per-pack pointer

## Critical: no src vendoring (Task 3 design fix)
Prior (Task 2 hello) vendored entire `src/dsm_ae` (~780KB+) into every task environment/.
**Do not do this.** It multiplies waste across 22+ packs.

Preferred Dockerfile (generated):
```dockerfile
FROM python:3.11-slim
WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e .
WORKDIR /app
# pack-specific fixtures only
COPY harbor_tasks/dsm-ae/<pack>/environment/fixtures/ /app/
...
```
Build context **must be repo root**.

## How to run harbor with monorepo context
From the dsm-ae repo root (so COPY src reaches the shared package):
```
harbor run -p harbor_tasks/dsm-ae/<pack_id> -a oracle
# or with model, dataset, k etc.
harbor run -p harbor_tasks/dsm-ae/tool_integrity_tier2 -a claude-code -m anthropic/claude-...
```

If your harbor invocation uses explicit docker build context (recommended for monorepo):
```
harbor run -p harbor_tasks/dsm-ae/<pack_id> --build-context . --dockerfile harbor_tasks/dsm-ae/<pack_id>/environment/Dockerfile ...
```
(Exact flags depend on harbor version; -p points at task metadata, context provides src/ + pyproject.)

## Docker label + harbor_runs persist (Task 1b)
Containers **must** be labeled for cleanup:
```
docker ... --label dsm-ae.harbor.job=${JOB_ID}
# or harbor passthrough of labels
```

After run (agent + verifier), persist using:
```python
from dsm_ae.harbor.run_layout import init_run, persist_reward, persist_trajectory, persist_logs, finalize_meta
from dsm_ae.harbor.runner import run_harbor_task

root = init_run(job_id, model=..., packs=[pack_id])
persist_reward(root, pack_id, trial_index, json.load(open("/logs/verifier/reward.json")))
# trajectories from /logs/agent/* if captured during agent phase
persist_trajectory(root, pack_id, trial_index, agent_traj_dir)
...
finalize_meta(...)
```

Always wrap:
```python
run_harbor_task(job_id=job_id, model=..., packs=[pack], task_fn=invoke_fn)
```
Guarantees `cleanup_docker_for_job(job_id)` (removes labeled containers) + `docker_cleanup.json` in `reports/harbor_runs/{job_id}/`

Layout:
reports/harbor_runs/{job_id}/
  meta.json
  rewards/<pack>__tN.json
  trajectories/<pack>__tN/...
  docker_cleanup.json
  ...

## Regenerating
python scripts/harbor_export_all_packs.py --out harbor_tasks
(will overwrite; git rm any old vendored trees under environment/src if present)

Generated for all packs in registry.

## Task 4: Multi-step / k-trial mapping (default outer loop)

**Mapping decision (per plan + brief):**
- **Default for k trials:** OUTER LOOP. One Harbor task execution = 1 trial (1 seed/persona).
  The `scripts/harbor_run_job.py` (or queue integration) loops `for pack in packs: for t in range(k): run trial t`.
  This keeps each Harbor task.toml simple (no [[steps]] bloat) and matches existing DSM-AE `k_trials` in ScaffoldCard + parallelizable runs.
- Use Harbor `[[steps]]` **only** when a *single trial* has sequential dependencies requiring separate phases (setup container → agent run → verifier).
  Example (only if needed):
  ```toml
  [[steps]]
  name = "setup_gold"
  [[steps]]
  name = "agent"
  [[steps]]
  name = "verify"
  ```

**tool_integrity_tier2 special case:**
- Fault injection (GoldReadFault for hard arm: first gold read_file returns transient error; agent must list/retry and not fabricate) is handled *inside* the pack `run_trial` + `GoldReadFaultAdapter`.
- No `[[steps]]` for it (avoids heavy toml); documented in `tool_integrity_tier2/task.toml` (gold_read_fault + notes) and its README.md.
- When using real agent in Harbor (not oracle/mock), the agent phase inside container will exercise the same pack code paths (fault wrapper active for hard scenario).

**harbor_run_job.py usage (offline mock supported):**
```
python scripts/harbor_run_job.py --job-id j1234567 --model mock/well_attuned --packs hello_metacog,tool_integrity_tier2 --k 2
```
- Produces `reports/harbor_runs/j1234567/rewards/{pack}__t{i}.json` + trajectories/
- Always runs `cleanup_docker_for_job(job_id)` in finally (labels: `dsm-ae.harbor.job={job_id}`)
- Mock path: task_fn uses `pack_bridge.score_workspace` + `prepare_workspace` (no `harbor` CLI or docker needed).
- For live: caller supplies task_fn that does `harbor run -p harbor_tasks/dsm-ae/<pack> ...` (with label).

See:
- .superpowers/sdd/task-4-brief.md
- docs/superpowers/plans/2026-07-17-harbor-pack-migration.md (Task 4 section)
- src/dsm_ae/harbor/runner.py (label docs)
- src/dsm_ae/harbor/pack_bridge.py (mock path)