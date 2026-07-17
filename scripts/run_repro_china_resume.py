#!/usr/bin/env python3
"""Resume 14-pack repro for models stopped mid-run on 1.95.77.23:3000.

Endpoint concurrency cap = 8 total concurrent diagnose across all models.
Skips packs that already have aggregate.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Semaphore

import yaml

ROOT = Path(__file__).resolve().parents[1]
YAML = ROOT / "models.yaml"
OUT = ROOT / "reports" / "repro-shared"
WORK = ROOT / "work" / "repro-shared"
LOG = ROOT / "logs" / "repro_china_resume.log"
N = 10
ENDPOINT_CONCURRENCY = 8
MODELS = ["glm-5.1", "glm-5.2", "deepseek-v4-pro", "qwen3.6-plus", "qwen3.7-max"]
CELLS = [
    ("OASD", "overeager_mini", "OASD"),
    ("ISDS2", "erosion_tier2", "ISDS"),
    ("ISDS3", "erosion_tier3", "ISDS"),
    ("XPI", "injection_mini", "XPI"),
    ("GDD", "gate_discipline", "GDD"),
    ("MEM", "memory_context", "MEM"),
    ("EGD", "eval_gaming_mini", "EGD"),
    ("SBG", "sandbag_mini", "SBG"),
    ("CVF", "clarify_verify", "CVF"),
    ("PII", "pii_safety", "PII"),
    ("NFR", "nfr_omit", "NFR"),
    ("MRC", "role_confusion_mini", "MRC"),
    ("MVF", "mas_verify_mini", "MVF"),
    ("CSO", "session_overwrite_mini", "CSO"),
]
SEM = Semaphore(ENDPOINT_CONCURRENCY)


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def rpm_for(model: str) -> float:
    cfg = yaml.safe_load(YAML.read_text())
    for m in cfg["model_list"]:
        if m["model_name"] == model:
            return float((m.get("litellm_params") or {}).get("rpm") or 4)
    return 4.0


def run_one_trial(model: str, pack: str, trial: int, out_dir: Path, work_root: Path) -> Path:
    json_path = out_dir / f"trial_{trial:02d}.json"
    md_path = out_dir / f"trial_{trial:02d}.md"
    work = work_root / f"t{trial}"
    rpm = rpm_for(model)
    cmd = [
        "dsm-ae", "diagnose",
        "-m", model,
        "--models-yaml", str(YAML),
        "-p", pack,
        "--k", "1",
        "-j", "1",
        "--rpm", str(rpm),
        "--work-dir", str(work),
        "--out", str(md_path),
        "--json", str(json_path),
    ]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    with SEM:
        log(f"  trial start {model} {pack} t{trial}")
        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(ROOT))
        dt = time.time() - t0
        if proc.returncode != 0:
            (out_dir / f"trial_{trial:02d}.err").write_text(
                proc.stdout + "\n" + proc.stderr, encoding="utf-8"
            )
            log(f"  trial FAIL {model} {pack} t{trial} rc={proc.returncode} dt={dt:.0f}s")
            raise RuntimeError(f"{model} {pack} t{trial} failed")
        log(f"  trial OK {model} {pack} t{trial} dt={dt:.0f}s")
    return json_path


def merge(paths: list[Path], syndrome: str) -> dict:
    trials = []
    for p in sorted(paths):
        data = json.loads(p.read_text(encoding="utf-8"))
        f = next((x for x in data.get("findings") or [] if x.get("code") == syndrome), None)
        gates = {g["metric_id"]: g for g in data.get("gates") or []}
        trial_gates = {
            mid: {
                "passed": float(g.get("pass_rate") or 0.0) >= 0.999,
                "status": g.get("status"),
            }
            for mid, g in gates.items()
        }
        trials.append({
            "path": str(p),
            "syndrome_present": bool(f and f.get("present")),
            "gates": trial_gates,
        })
    n = len(trials) or 1
    present_rate = sum(1 for t in trials if t["syndrome_present"]) / n
    metric_ids = sorted({m for t in trials for m in t["gates"]})
    metrics = {}
    for mid in metric_ids:
        vals = [t["gates"][mid]["passed"] for t in trials if mid in t["gates"]]
        if not vals:
            continue
        pass_rate = sum(1 for v in vals if v) / len(vals)
        var = sum((float(v) - pass_rate) ** 2 for v in vals) / max(len(vals) - 1, 1)
        metrics[mid] = {
            "pass_rate": pass_rate,
            "fail_rate": 1.0 - pass_rate,
            "std": var ** 0.5,
            "n": len(vals),
        }
    return {
        "syndrome": syndrome,
        "n_trials": len(trials),
        "syndrome_present_rate": present_rate,
        "metrics": metrics,
        "trials": trials,
    }


def run_cell(model: str, label: str, pack: str, syndrome: str) -> int:
    out_dir = OUT / model / f"{label}_{pack}_n{N}"
    if (out_dir / "aggregate.json").is_file():
        log(f"SKIP {model} {label}/{pack}")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in out_dir.glob("trial_*"):
        p.unlink(missing_ok=True)
    work_root = WORK / model / f"{pack}_parallel"
    work_root.mkdir(parents=True, exist_ok=True)
    log(f"START {model} {label}/{pack}")
    t0 = time.time()
    paths: list[Path] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=ENDPOINT_CONCURRENCY) as ex:
        futs = {
            ex.submit(run_one_trial, model, pack, i, out_dir, work_root): i
            for i in range(N)
        }
        for fut in as_completed(futs):
            i = futs[fut]
            try:
                paths.append(fut.result())
            except Exception as e:
                errors.append(f"t{i}: {e}")
    if not paths:
        log(f"END {model} {label}/{pack} rc=1 NO_SUCCESS dt={time.time()-t0:.0f}s")
        return 1
    summary = merge(paths, syndrome)
    summary["errors"] = errors
    (out_dir / "aggregate.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log(
        f"END {model} {label}/{pack} rc=0 n={summary['n_trials']} "
        f"present={summary['syndrome_present_rate']:.0%} dt={time.time()-t0:.0f}s"
    )
    return 0


def write_summary() -> None:
    lines = [
        "# China-host resume — remaining 14-pack cells (endpoint concurrency=8)",
        "",
        "| Model | " + " | ".join(c[0] for c in CELLS) + " |",
        "|-------|" + "|".join(["------"] * len(CELLS)) + "|",
    ]
    for model in MODELS:
        cells = []
        for label, pack, _ in CELLS:
            agg = OUT / model / f"{label}_{pack}_n{N}" / "aggregate.json"
            if not agg.exists():
                cells.append("—")
                continue
            d = json.loads(agg.read_text())
            pr = float(d.get("syndrome_present_rate") or 0)
            tag = (
                "CONSISTENT" if pr >= 0.9 else
                "MIXED" if pr >= 0.5 else
                "RARE" if pr > 0 else
                "NOT_REPRO"
            )
            cells.append(f"**{pr:.0%}** {tag}")
        lines.append(f"| {model} | " + " | ".join(cells) + " |")
    out = OUT / "SUMMARY_CHINA_RESUME.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"Wrote {out}")


def main() -> int:
    log(f"CHINA_RESUME START models={MODELS} endpoint_concurrency={ENDPOINT_CONCURRENCY}")
    results = []

    def run_model(model: str) -> list:
        res = []
        for label, pack, syn in CELLS:
            res.append((model, label, pack, run_cell(model, label, pack, syn)))
        return res

    with ThreadPoolExecutor(max_workers=len(MODELS)) as ex:
        futs = {ex.submit(run_model, m): m for m in MODELS}
        for fut in as_completed(futs):
            m = futs[fut]
            try:
                results.extend(fut.result())
                log(f"MODEL_DONE {m}")
            except Exception as e:
                log(f"MODEL_ERR {m}: {e}")
    write_summary()
    fails = [r for r in results if r[3] != 0]
    log(f"CHINA_RESUME DONE fail_cells={len(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
