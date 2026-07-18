#!/usr/bin/env python3
"""
Harbor job runner for DSM-AE packs (Task 4).

Orchestrates k trials (outer loop) over packs for a single job_id.

- Writes artifacts to reports/harbor_runs/{job_id}/rewards/{pack}__t{i}.json
  and trajectories/{pack}__t{i}/...
- Uses run_harbor_task wrapper (guarantees cleanup_docker_for_job in finally)
- Offline mock supported: task_fn that calls pack_bridge.prepare_workspace + score_workspace
  (no harbor CLI, no docker required). Uses MockClient via bridge.
- For real harbor runs: pass a task_fn that invokes `harbor run` (the fn receives the job run_dir).
- Docker containers (when used) must be started with:
    --label dsm-ae.harbor.job={job_id}
  (or harbor equivalent). Cleanup always happens.

CLI:
  python scripts/harbor_run_job.py --job-id abc12def --model mock/well_attuned \
      --packs hello_metacog,tool_integrity_tier2 --k 3
  # or with --base /tmp/harbor_test for sandbox

Returns the job root path on success. Exits non-zero on failure (but cleanup ran).

See:
- harbor_tasks/dsm-ae/README.md
- src/dsm_ae/harbor/runner.py
- .superpowers/sdd/task-4-brief.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# ensure src importable when run as script
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from dsm_ae.harbor.pack_bridge import prepare_workspace, score_workspace, write_reward
from dsm_ae.harbor.run_layout import init_run, finalize_meta
from dsm_ae.harbor.runner import run_harbor_task


def _infer_persona(model: str) -> str:
    if model.startswith("mock/"):
        p = model.split("/", 1)[1] or "well_attuned"
        return p
    # For live models, default well_attuned for mock scoring in offline paths;
    # real agent phase will not use this persona.
    return "well_attuned"


def _mock_task_fn(pack_id: str, trial_index: int, model: str):
    """Return a task_fn suitable for run_harbor_task that performs offline scoring.

    The fn receives the job's run_dir (harbor_runs root), prepares the workspace metadata,
    runs score_workspace (which for mock will execute pack.run_trial via Mock + persist traj/scores),
    and returns the reward dict (harbor shape with floats) so runner can persist_reward.
    Trajectories are already written to the correct layout location by score_workspace.
    """
    persona = _infer_persona(model)

    def task_fn(run_dir: Path) -> dict[str, Any]:
        # Ensure layout dirs (idempotent)
        (run_dir / "rewards").mkdir(parents=True, exist_ok=True)
        (run_dir / "trajectories").mkdir(parents=True, exist_ok=True)

        # Prepare (records persona for any re-score) + score (runs mock trial if no prior scores)
        prepare_workspace(pack_id, run_dir, trial_index, mock_persona=persona)
        metrics = score_workspace(pack_id, run_dir, trial_index)

        # Build harbor reward floats (primary_pass + metric values)
        tmp_rew = run_dir / f".tmp_reward_{pack_id}__t{trial_index}.json"
        write_reward(metrics, tmp_rew)
        reward = json.loads(tmp_rew.read_text(encoding="utf-8"))
        # clean tmp
        try:
            tmp_rew.unlink()
        except Exception:
            pass
        return reward

    return task_fn


def run_harbor_job(
    *,
    job_id: str,
    model: str,
    packs: list[str],
    k: int = 1,
    run_dir_base: Path | None = None,
    reports_dir: Path | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> Path:
    """Run k outer-loop trials for the given packs under one job_id.

    Always ensures cleanup (via runner). Returns the harbor_runs/{job_id} root.
    Supports pure-offline execution via mock task_fns.
    """
    if not job_id or not packs:
        raise ValueError("job_id and packs required")
    k = max(1, int(k))

    # Initialize once (records full context); subsequent runner calls will update meta/status
    root = init_run(
        job_id,
        reports_dir=reports_dir,
        base=run_dir_base,
        model=model,
        packs=packs,
        k_trials=k,
        **(extra_meta or {}),
    )

    overall_status = "succeeded"
    errors: list[str] = []

    try:
        for pack_id in packs:
            for ti in range(k):
                print(f"[harbor_run_job] pack={pack_id} trial={ti} model={model}")
                tf = _mock_task_fn(pack_id, ti, model)
                try:
                    run_harbor_task(
                        job_id=job_id,
                        model=model,
                        packs=packs,
                        run_dir_base=run_dir_base,
                        reports_dir=reports_dir,
                        task_fn=tf,
                        pack_id=pack_id,
                        trial_i=ti,
                        # reward= not needed; returned by tf and auto-persisted by runner when primary_pass present
                    )
                except Exception as e:
                    errors.append(f"{pack_id}__t{ti}: {e}")
                    overall_status = "partial"
                    # continue other trials; cleanup still happens inside the runner call

        # final meta
        finalize_meta(
            root,
            {
                "status": overall_status if not errors else "partial",
                "k_trials": k,
                "errors": errors if errors else None,
            },
        )
        if errors:
            print(f"[harbor_run_job] completed with {len(errors)} trial errors")
    finally:
        # Note: per-trial runner calls already ran cleanup; this is belt-and-suspenders
        # (cleanup is idempotent). We do not call run_harbor_task here to avoid re-init.
        pass

    return root


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run DSM-AE packs as Harbor job (k trials, outer loop, offline mock supported)")
    p.add_argument("--job-id", required=True, help="Job id (8+ chars, used for reports/harbor_runs/{job_id} and docker labels)")
    p.add_argument("--model", required=True, help="e.g. mock/well_attuned or gpt-... (mock/* enables offline scoring)")
    p.add_argument("--packs", required=True, help="Comma separated pack ids, e.g. hello_metacog,tool_integrity_tier2")
    p.add_argument("--k", type=int, default=1, help="Number of trials (outer loop)")
    p.add_argument("--base", type=Path, default=None, help="Override base dir for job root (for tests: direct parent)")
    p.add_argument("--reports-dir", type=Path, default=None, help="reports dir (default: ./reports)")
    p.add_argument("--extra-meta", type=str, default=None, help='JSON string for extra meta in job meta.json')
    args = p.parse_args(argv)

    packs = [x.strip() for x in args.packs.split(",") if x.strip()]
    extra = None
    if args.extra_meta:
        try:
            extra = json.loads(args.extra_meta)
        except Exception as e:
            print(f"WARNING: bad --extra-meta JSON ignored: {e}")

    try:
        root = run_harbor_job(
            job_id=args.job_id,
            model=args.model,
            packs=packs,
            k=args.k,
            run_dir_base=args.base,
            reports_dir=args.reports_dir,
            extra_meta=extra,
        )
        print(f"harbor job complete: {root}")
        # also print a summary reward location
        print("rewards:")
        for r in sorted((root / "rewards").glob("*.json")):
            print("  ", r)
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        # cleanup should have run inside any runner invocations
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
