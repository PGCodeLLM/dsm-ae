#!/usr/bin/env python3
"""Run k independent 1-trial diagnose jobs in parallel (10 sub-agents style).

Each worker writes a single-trial JSON; this script merges gates by averaging
per-trial passed flags so we can report symptom rate = fail_rate over 10 trials.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def run_one(
    *,
    model: str,
    pack: str,
    trial: int,
    yaml: Path,
    out_dir: Path,
    work_root: Path,
    rpm: float,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    work = work_root / f"t{trial}"
    json_path = out_dir / f"trial_{trial:02d}.json"
    md_path = out_dir / f"trial_{trial:02d}.md"
    cmd = [
        "dsm-ae",
        "diagnose",
        "-m",
        model,
        "--models-yaml",
        str(yaml),
        "-p",
        pack,
        "--k",
        "1",
        "-j",
        "1",
        "--rpm",
        str(rpm),
        "--work-dir",
        str(work),
        "--out",
        str(md_path),
        "--json",
        str(json_path),
    ]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    dt = time.time() - t0
    if proc.returncode != 0:
        (out_dir / f"trial_{trial:02d}.err").write_text(
            proc.stdout + "\n" + proc.stderr, encoding="utf-8"
        )
        raise RuntimeError(f"trial {trial} failed rc={proc.returncode} ({dt:.1f}s)")
    return json_path


def merge_trials(paths: list[Path], syndrome: str) -> dict:
    trials = []
    for p in sorted(paths):
        data = json.loads(p.read_text(encoding="utf-8"))
        f = next((x for x in data.get("findings") or [] if x.get("code") == syndrome), None)
        gates = {g["metric_id"]: g for g in data.get("gates") or []}
        # k=1 => pass_rate is 0 or 1
        trial_gates = {
            mid: {
                "passed": float(g.get("pass_rate") or 0.0) >= 0.999,
                "status": g.get("status"),
                "value": g.get("mean"),
            }
            for mid, g in gates.items()
        }
        trials.append(
            {
                "path": str(p),
                "syndrome_present": bool(f and f.get("present")),
                "severity": (f or {}).get("severity"),
                "gates": trial_gates,
            }
        )

    n = len(trials) or 1
    present_rate = sum(1 for t in trials if t["syndrome_present"]) / n
    # metric fail rates
    metric_ids = sorted({m for t in trials for m in t["gates"]})
    metrics = {}
    for mid in metric_ids:
        vals = [t["gates"][mid]["passed"] for t in trials if mid in t["gates"]]
        if not vals:
            continue
        pass_rate = sum(1 for v in vals if v) / len(vals)
        # sample std of bernoulli
        mean = pass_rate
        var = sum((float(v) - mean) ** 2 for v in vals) / max(len(vals) - 1, 1)
        metrics[mid] = {
            "pass_rate": pass_rate,
            "fail_rate": 1.0 - pass_rate,
            "std": var**0.5,
            "n": len(vals),
        }

    return {
        "syndrome": syndrome,
        "n_trials": len(trials),
        "syndrome_present_rate": present_rate,
        "metrics": metrics,
        "trials": trials,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--model", required=True)
    ap.add_argument("-p", "--pack", required=True)
    ap.add_argument("--syndrome", required=True, help="Syndrome code e.g. CTX")
    ap.add_argument("-n", "--n-trials", type=int, default=10)
    ap.add_argument("-j", "--workers", type=int, default=3, help="Parallel sub-agents")
    ap.add_argument("--models-yaml", type=Path, default=Path("models.yaml"))
    ap.add_argument("--rpm", type=float, default=4.0)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--work-root", type=Path, required=True)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.work_root.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {
            ex.submit(
                run_one,
                model=args.model,
                pack=args.pack,
                trial=i,
                yaml=args.models_yaml,
                out_dir=args.out_dir,
                work_root=args.work_root,
                rpm=args.rpm / max(args.workers, 1),
            ): i
            for i in range(args.n_trials)
        }
        for fut in as_completed(futs):
            i = futs[fut]
            try:
                p = fut.result()
                paths.append(p)
                print(f"OK trial {i} → {p}", flush=True)
            except Exception as e:
                errors.append(f"trial {i}: {e}")
                print(f"ERR trial {i}: {e}", flush=True)

    if not paths:
        print("No successful trials", file=sys.stderr)
        return 1
    summary = merge_trials(paths, args.syndrome)
    summary["errors"] = errors
    out = args.out_dir / "aggregate.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("syndrome", "n_trials", "syndrome_present_rate", "metrics")}, indent=2))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
