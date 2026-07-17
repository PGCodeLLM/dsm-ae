#!/usr/bin/env python3
"""Orchestrate shared-symptom repro: 10 parallel 1-trial agents per (model, pack)."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CELLS = [
    ("CTX", "coord_tax_mini"),
    ("RSD", "sycophancy_mini"),
    ("TID", "tool_integrity"),
    ("MAH", "handoff_mini"),
    ("PCD", "loop_control"),
    ("MCD", "hello_metacog"),
    ("ISDS", "slop_indicator"),
]
MODELS = {
    "gpt-5.5": {"rpm": 6.0, "workers": 2},
    "grok-build": {"rpm": 4.0, "workers": 2},
}
N = 10
YAML = ROOT / "models.yaml"
OUT = ROOT / "reports" / "repro-shared"
WORK = ROOT / "work" / "repro-shared"
LOG = ROOT / "logs" / "repro_orchestrator.log"


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_cell(model: str, code: str, pack: str) -> int:
    cfg = MODELS[model]
    out_dir = OUT / model / f"{code}_{pack}_n{N}"
    work = WORK / model / f"{pack}_parallel"
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run_repro_10_parallel_trials.py"),
        "-m", model,
        "-p", pack,
        "--syndrome", code,
        "-n", str(N),
        "-j", str(cfg["workers"]),
        "--rpm", str(cfg["rpm"]),
        "--models-yaml", str(YAML),
        "--out-dir", str(out_dir),
        "--work-root", str(work),
    ]
    log(f"START {model} {code}/{pack}")
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(ROOT))
    log(f"END {model} {code}/{pack} rc={proc.returncode} dt={time.time()-t0:.0f}s")
    return proc.returncode


def main() -> int:
    log(f"ORCH START n={N} cells={len(CELLS)} models={list(MODELS)}")
    results = []
    for code, pack in CELLS:
        with ThreadPoolExecutor(max_workers=2) as ex:
            futs = {ex.submit(run_cell, model, code, pack): model for model in MODELS}
            for fut in as_completed(futs):
                model = futs[fut]
                try:
                    rc = fut.result()
                    results.append((model, code, pack, rc))
                except Exception as e:
                    log(f"ERR {model} {code}: {e}")
                    results.append((model, code, pack, 1))

    lines = [
        "# Shared-symptom reproducibility — 10 parallel trials",
        "",
        "Each cell: **10 independent 1-trial agents** (parallel workers).",
        "",
        "| Model | Syndrome | Pack | n | present_rate | Key fail rates |",
        "|-------|----------|------|---|--------------|----------------|",
    ]
    for model in MODELS:
        for code, pack in CELLS:
            agg = OUT / model / f"{code}_{pack}_n{N}" / "aggregate.json"
            if not agg.exists():
                lines.append(f"| {model} | {code} | `{pack}` | — | NO_DATA | — |")
                continue
            d = json.loads(agg.read_text())
            mets = d.get("metrics") or {}
            fails = sorted(
                ((m, v["fail_rate"], v["std"]) for m, v in mets.items()),
                key=lambda x: -x[1],
            )[:4]
            fail_s = "; ".join(f"`{m}` {fr:.0%} (σ={sd:.2f})" for m, fr, sd in fails) or "—"
            lines.append(
                f"| {model} | **{code}** | `{pack}` | {d.get('n_trials')} | "
                f"**{d.get('syndrome_present_rate', 0):.0%}** | {fail_s} |"
            )
    out = OUT / "SUMMARY_PARALLEL.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"Wrote {out}")
    log(f"ORCH DONE results={results}")
    return 0 if all(r[3] == 0 for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
