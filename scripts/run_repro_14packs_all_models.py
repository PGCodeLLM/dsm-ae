#!/usr/bin/env python3
"""Run remaining 14 packs × 10 trials for all models.yaml models (concurrent models)."""
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
OUT_ROOT = ROOT / "reports" / "repro-shared"
WORK_ROOT = ROOT / "work" / "repro-shared"
LOG = ROOT / "logs" / "repro_14packs.log"
N = 10
DEFAULT_WORKERS = 2

# Remaining packs (not in first shared-7 study) with primary syndrome codes
CELLS = [
    ("OASD", "overeager_mini"),
    ("ISDS2", "erosion_tier2"),   # ISDS tier2 metrics
    ("ISDS3", "erosion_tier3"),
    ("XPI", "injection_mini"),
    ("GDD", "gate_discipline"),
    ("MEM", "memory_context"),
    ("EGD", "eval_gaming_mini"),
    ("SBG", "sandbag_mini"),
    ("CVF", "clarify_verify"),
    ("PII", "pii_safety"),
    ("NFR", "nfr_omit"),
    ("MRC", "role_confusion_mini"),
    ("MVF", "mas_verify_mini"),
    ("CSO", "session_overwrite_mini"),
]

# Syndrome code used when scoring findings in diagnose output
SYNDROME_FOR_PACK = {
    "overeager_mini": "OASD",
    "erosion_tier2": "ISDS",
    "erosion_tier3": "ISDS",
    "injection_mini": "XPI",
    "gate_discipline": "GDD",
    "memory_context": "MEM",
    "eval_gaming_mini": "EGD",
    "sandbag_mini": "SBG",
    "clarify_verify": "CVF",
    "pii_safety": "PII",
    "nfr_omit": "NFR",
    "role_confusion_mini": "MRC",
    "mas_verify_mini": "MVF",
    "session_overwrite_mini": "CSO",
}


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_models() -> list[tuple[str, float]]:
    cfg = yaml.safe_load(YAML.read_text())
    out = []
    seen = set()
    for m in cfg["model_list"]:
        name = m["model_name"]
        if name.startswith("hosted_vllm/") or name in seen:
            continue
        seen.add(name)
        rpm = float((m.get("litellm_params") or {}).get("rpm") or 4)
        out.append((name, rpm))
    return out


def cell_done(model: str, label: str, pack: str) -> bool:
    agg = OUT_ROOT / model / f"{label}_{pack}_n{N}" / "aggregate.json"
    return agg.is_file()


def run_cell(model: str, label: str, pack: str, rpm: float) -> tuple[str, str, str, int, float]:
    syndrome = SYNDROME_FOR_PACK[pack]
    out_dir = OUT_ROOT / model / f"{label}_{pack}_n{N}"
    work = WORK_ROOT / model / f"{pack}_parallel"
    out_dir.mkdir(parents=True, exist_ok=True)
    # clear previous debris for this cell
    for p in out_dir.glob("trial_*"):
        p.unlink(missing_ok=True)
    (out_dir / "aggregate.json").unlink(missing_ok=True)

    workers = 2 if rpm >= 4 else 1
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run_repro_10_parallel_trials.py"),
        "-m", model,
        "-p", pack,
        "--syndrome", syndrome,
        "-n", str(N),
        "-j", str(workers),
        "--rpm", str(rpm),
        "--models-yaml", str(YAML),
        "--out-dir", str(out_dir),
        "--work-root", str(work),
    ]
    log(f"START {model} {label}/{pack}")
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(ROOT))
    dt = time.time() - t0
    log(f"END {model} {label}/{pack} rc={proc.returncode} dt={dt:.0f}s")
    return model, label, pack, proc.returncode, dt


def run_model(model: str, rpm: float) -> list:
    results = []
    for label, pack in CELLS:
        if cell_done(model, label, pack):
            log(f"SKIP {model} {label}/{pack} (already have aggregate)")
            results.append((model, label, pack, 0, 0.0))
            continue
        results.append(run_cell(model, label, pack, rpm))
    return results


def write_report() -> Path:
    """Build cross-model report for the 14 packs + note the original 7."""
    models = [m for m, _ in load_models()]
    lines = [
        "# Reproducibility study — remaining 14 packs (k=10 independent trials)",
        "",
        "Scope: packs **not** in the original shared-7 mini-testbeds, to find "
        "diagnoses that fail to reproduce or are borderline under n=10.",
        "",
        "## Pack → syndrome",
        "",
        "| Label | Pack | Syndrome code |",
        "|-------|------|---------------|",
    ]
    for label, pack in CELLS:
        lines.append(f"| {label} | `{pack}` | {SYNDROME_FOR_PACK[pack]} |")

    lines += [
        "",
        "## Results matrix (syndrome present_rate over 10 trials)",
        "",
    ]
    # header
    labels = [c[0] for c in CELLS]
    lines.append("| Model | " + " | ".join(labels) + " |")
    lines.append("|-------|" + "|".join(["------"] * len(labels)) + "|")

    for model in models:
        cells = []
        for label, pack in CELLS:
            agg = OUT_ROOT / model / f"{label}_{pack}_n{N}" / "aggregate.json"
            if not agg.exists():
                cells.append("—")
                continue
            d = json.loads(agg.read_text())
            pr = d.get("syndrome_present_rate")
            n = d.get("n_trials", 0)
            if pr is None:
                cells.append("?")
                continue
            # classify
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

    lines += [
        "",
        "## Detailed gate fails (present_rate > 0 or any fail)",
        "",
    ]
    for model in models:
        any_detail = False
        block = [f"### {model}", ""]
        for label, pack in CELLS:
            agg = OUT_ROOT / model / f"{label}_{pack}_n{N}" / "aggregate.json"
            if not agg.exists():
                continue
            d = json.loads(agg.read_text())
            pr = float(d.get("syndrome_present_rate") or 0)
            mets = d.get("metrics") or {}
            fails = [(m, v["fail_rate"], v["std"]) for m, v in mets.items() if v.get("fail_rate", 0) > 0]
            if pr == 0 and not fails:
                continue
            any_detail = True
            fails.sort(key=lambda x: -x[1])
            fs = "; ".join(f"`{m}` fail {fr:.0%} (σ={sd:.2f})" for m, fr, sd in fails[:6]) or "—"
            block.append(f"- **{label}** (`{pack}`): present **{pr:.0%}** · {fs}")
        if any_detail:
            lines.extend(block)
            lines.append("")

    lines += [
        "",
        "## Legend",
        "",
        "- **CONSISTENT** — syndrome present ≥90% of trials",
        "- **MIXED** — 50–89% (borderline / unstable)",
        "- **RARE** — 1–49%",
        "- **NOT_REPRO** — 0% present under n=10",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    out = OUT_ROOT / "SUMMARY_14PACKS.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # also refresh combined
    combined = OUT_ROOT / "SUMMARY_ALL.md"
    prev7 = OUT_ROOT / "SUMMARY_PARALLEL.md"
    parts = ["# Full reproducibility report\n"]
    if (OUT_ROOT / "gpt-5.5").exists() or (OUT_ROOT / "grok-build").exists():
        parts.append("## Original shared-7 packs\n\nSee per-model dirs and `SUMMARY_GROK.md` / gpt-5.5 aggregates.\n")
    parts.append(out.read_text())
    combined.write_text("\n".join(parts), encoding="utf-8")
    log(f"Wrote {out} and {combined}")
    return out


def main() -> int:
    models = load_models()
    log(f"14PACKS START models={len(models)} packs={len(CELLS)} n={N}")
    log(f"models: {[m for m,_ in models]}")
    all_results = []
    # Concurrent models
    with ThreadPoolExecutor(max_workers=len(models)) as ex:
        futs = {ex.submit(run_model, m, rpm): m for m, rpm in models}
        for fut in as_completed(futs):
            m = futs[fut]
            try:
                res = fut.result()
                all_results.extend(res)
                log(f"MODEL_DONE {m}")
            except Exception as e:
                log(f"MODEL_ERR {m}: {e}")
    write_report()
    fails = [r for r in all_results if r[3] != 0]
    log(f"14PACKS DONE fail_cells={len(fails)} total={len(all_results)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
