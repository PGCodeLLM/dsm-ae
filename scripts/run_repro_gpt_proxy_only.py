#!/usr/bin/env python3
"""Continue 14-pack (and optional TID2) repro for GPT proxy models only.

Skips completed aggregates. Waits if a model already has a running diagnose/parallel
job so we don't clobber in-flight trials. Does not touch non-GPT models.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
YAML = ROOT / "models.yaml"
OUT = ROOT / "reports" / "repro-shared"
WORK = ROOT / "work" / "repro-shared"
LOG = ROOT / "logs" / "repro_gpt_proxy_only.log"
N = 10

GPT_MODELS = ["gpt-5.5", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6-luna"]
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
# also ensure TID2 if missing
EXTRA = [("TID2", "tool_integrity_tier2", "TID")]


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
            return float((m.get("litellm_params") or {}).get("rpm") or 6)
    return 6.0


def model_busy(model: str) -> bool:
    try:
        out = subprocess.check_output(["ps", "aux"], text=True)
    except Exception:
        return False
    for line in out.splitlines():
        if f"-m {model}" in line or f"-m {model} " in line:
            if "dsm-ae diagnose" in line or "run_repro_10_parallel_trials" in line:
                return True
    return False


def wait_idle(model: str, timeout: float = 7200) -> None:
    t0 = time.time()
    while model_busy(model):
        if time.time() - t0 > timeout:
            log(f"WAIT_TIMEOUT {model}")
            return
        time.sleep(15)


def run_cell(model: str, label: str, pack: str, syndrome: str) -> int:
    out_dir = OUT / model / f"{label}_{pack}_n{N}"
    if (out_dir / "aggregate.json").is_file():
        log(f"SKIP {model} {label}/{pack}")
        return 0
    wait_idle(model)
    # re-check after wait
    if (out_dir / "aggregate.json").is_file():
        log(f"SKIP {model} {label}/{pack} (completed while waiting)")
        return 0
    rpm = rpm_for(model)
    work = WORK / model / f"{pack}_parallel"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run_repro_10_parallel_trials.py"),
        "-m", model,
        "-p", pack,
        "--syndrome", syndrome,
        "-n", str(N),
        "-j", "2",
        "--rpm", str(rpm),
        "--models-yaml", str(YAML),
        "--out-dir", str(out_dir),
        "--work-root", str(work),
    ]
    log(f"START {model} {label}/{pack}")
    t0 = time.time()
    # Do not wipe in-progress: parallel script may create fresh trials in out_dir
    # Only clear if no live workers (we waited idle)
    for p in out_dir.glob("trial_*"):
        p.unlink(missing_ok=True)
    rc = subprocess.run(cmd, cwd=str(ROOT)).returncode
    log(f"END {model} {label}/{pack} rc={rc} dt={time.time()-t0:.0f}s")
    return rc


def run_model(model: str) -> list:
    results = []
    for label, pack, syn in CELLS + EXTRA:
        results.append((model, label, pack, run_cell(model, label, pack, syn)))
    return results


def write_report() -> None:
    lines = [
        "# GPT proxy models — remaining packs (k=10)",
        "",
        "Models: " + ", ".join(f"`{m}`" for m in GPT_MODELS),
        "",
        "| Model | " + " | ".join(c[0] for c in CELLS + EXTRA) + " |",
        "|-------|" + "|".join(["------"] * (len(CELLS) + len(EXTRA))) + "|",
    ]
    for model in GPT_MODELS:
        cells = []
        for label, pack, _ in CELLS + EXTRA:
            agg = OUT / model / f"{label}_{pack}_n{N}" / "aggregate.json"
            if not agg.exists():
                cells.append("—")
                continue
            d = json.loads(agg.read_text())
            pr = float(d.get("syndrome_present_rate") or 0)
            if pr >= 0.9:
                tag = "CONSISTENT"
            elif pr >= 0.5:
                tag = "MIXED"
            elif pr > 0:
                tag = "RARE"
            else:
                tag = "NOT_REPRO"
            cells.append(f"**{pr:.0%}** {tag}")
        lines.append(f"| {model} | " + " | ".join(cells) + " |")
    out = OUT / "SUMMARY_GPT_PROXY.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"Wrote {out}")


def main() -> int:
    log(f"GPT_PROXY_ONLY START models={GPT_MODELS}")
    with ThreadPoolExecutor(max_workers=len(GPT_MODELS)) as ex:
        futs = {ex.submit(run_model, m): m for m in GPT_MODELS}
        for fut in as_completed(futs):
            m = futs[fut]
            try:
                fut.result()
                log(f"MODEL_DONE {m}")
            except Exception as e:
                log(f"MODEL_ERR {m}: {e}")
    write_report()
    log("GPT_PROXY_ONLY DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
