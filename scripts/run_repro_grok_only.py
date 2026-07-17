#!/usr/bin/env python3
"""Run shared-symptom repro for grok-build only: 10 parallel trials × 7 packs."""
from __future__ import annotations

import json
import subprocess
import sys
import time
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
MODEL = "grok-build"
N = 10
WORKERS = 2
RPM = 4.0
YAML = ROOT / "models.yaml"
OUT = ROOT / "reports" / "repro-shared" / MODEL
WORK = ROOT / "work" / "repro-shared" / MODEL
LOG = ROOT / "logs" / "repro_grok_only.log"


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    log(f"GROK-ONLY START n={N} cells={len(CELLS)}")
    results = []
    for code, pack in CELLS:
        out_dir = OUT / f"{code}_{pack}_n{N}"
        work = WORK / f"{pack}_parallel"
        # clear prior AUTH_FAIL debris so we only keep this run
        if out_dir.exists():
            for p in out_dir.glob("trial_*"):
                p.unlink(missing_ok=True)
            (out_dir / "aggregate.json").unlink(missing_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "run_repro_10_parallel_trials.py"),
            "-m", MODEL,
            "-p", pack,
            "--syndrome", code,
            "-n", str(N),
            "-j", str(WORKERS),
            "--rpm", str(RPM),
            "--models-yaml", str(YAML),
            "--out-dir", str(out_dir),
            "--work-root", str(work),
        ]
        log(f"START {code}/{pack}")
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=str(ROOT))
        dt = time.time() - t0
        log(f"END {code}/{pack} rc={proc.returncode} dt={dt:.0f}s")
        results.append((code, pack, proc.returncode, dt))

    lines = [
        "# grok-build shared-symptom reproducibility — 10 parallel trials",
        "",
        f"Token source: `~/.grok/auth.json` synced into `models.yaml`.",
        "",
        "| Syndrome | Pack | n | present_rate | Key fail rates |",
        "|----------|------|---|--------------|----------------|",
    ]
    for code, pack in CELLS:
        agg = OUT / f"{code}_{pack}_n{N}" / "aggregate.json"
        if not agg.exists():
            lines.append(f"| **{code}** | `{pack}` | — | NO_DATA | — |")
            continue
        d = json.loads(agg.read_text())
        mets = d.get("metrics") or {}
        fails = sorted(
            ((m, v["fail_rate"], v["std"]) for m, v in mets.items()),
            key=lambda x: -x[1],
        )[:4]
        fail_s = "; ".join(f"`{m}` {fr:.0%} (σ={sd:.2f})" for m, fr, sd in fails) or "—"
        lines.append(
            f"| **{code}** | `{pack}` | {d.get('n_trials')} | "
            f"**{d.get('syndrome_present_rate', 0):.0%}** | {fail_s} |"
        )
    out = OUT / "SUMMARY_GROK.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # also write combined summary with gpt if present
    combined = ROOT / "reports" / "repro-shared" / "SUMMARY_PARALLEL.md"
    combined.write_text(
        "# Shared-symptom reproducibility — 10 parallel trials\n\n"
        "## grok-build\n\n" + "\n".join(lines[3:]) + "\n"
        f"\nFull grok report: `reports/repro-shared/grok-build/SUMMARY_GROK.md`\n"
        f"Results: {results}\n",
        encoding="utf-8",
    )
    log(f"Wrote {out}")
    log(f"GROK-ONLY DONE results={results}")
    return 0 if all(r[2] == 0 for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
