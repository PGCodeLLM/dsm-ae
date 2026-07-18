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