#!/usr/bin/env python3
"""Progress monitor for 14-pack multi-model repro study."""
from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "reports" / "repro-shared"
LOG = ROOT / "logs" / "repro_14packs.log"
ERR_GLOB_ROOT = ROOT / "work" / "repro-shared"
MONITOR_MD = OUT_ROOT / "MONITOR_14PACKS.md"
EVENTS = OUT_ROOT / "MONITOR_14PACKS_EVENTS.log"
SUMMARY = OUT_ROOT / "SUMMARY_14PACKS.md"
STATE_FILE = OUT_ROOT / ".monitor_14packs_state.json"

CELLS = [
    ("OASD", "overeager_mini"),
    ("ISDS2", "erosion_tier2"),
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
LABELS = [c[0] for c in CELLS]
N = 10
POLL_SEC = 75
MODELS = [
    "gpt-5.5", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6-luna",
    "Beta_pangu_92b", "Beta_pangu_505b", "glm-5.1", "glm-5.2",
    "deepseek-v4-pro", "qwen3.6-plus", "qwen3.5-397b-a17b",
    "qwen3.7-max", "grok-build",
]


def now_str() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def classify(rate: float) -> str:
    if rate >= 0.9:
        return "CONSISTENT"
    if rate >= 0.5:
        return "MIXED"
    if rate > 0:
        return "RARE"
    return "NOT_REPRO"


def _ps_lines(match: str) -> list[str]:
    """List process cmdlines containing match, excluding this monitor and shells."""
    try:
        r = subprocess.run(["ps", "ax", "-o", "pid=,args="], capture_output=True, text=True)
    except Exception:
        return []
    out = []
    for line in r.stdout.splitlines():
        if match not in line:
            continue
        if "monitor_14packs" in line:
            continue
        if "grep" in line:
            continue
        out.append(line.strip())
    return out


def orchestrator_alive() -> tuple[bool, str]:
    lines = _ps_lines("run_repro_14packs_all_models.py")
    if lines:
        pid = lines[0].split(None, 1)[0]
        return True, pid
    return False, ""


def count_diagnose() -> int:
    return len(_ps_lines("dsm-ae diagnose"))


def load_aggregate(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def present_rate(agg: dict) -> float | None:
    for k in ("syndrome_present_rate", "present_rate", "rate"):
        if k in agg and isinstance(agg[k], (int, float)):
            return float(agg[k])
    if "trials" in agg and isinstance(agg["trials"], list):
        n = len(agg["trials"])
        if n:
            p = sum(1 for t in agg["trials"] if t.get("syndrome_present") or t.get("present"))
            return p / n
    return None


def current_packs_from_log() -> dict[str, str]:
    cur: dict[str, str] = {}
    if not LOG.is_file():
        return cur
    try:
        text = LOG.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return cur
    for line in text.splitlines():
        m = re.search(r"START (\S+) (\S+/\S+)", line)
        if m:
            cur[m.group(1)] = m.group(2) + " (running)"
        m = re.search(r"END (\S+) (\S+/\S+) rc=(\S+)", line)
        if m:
            cur[m.group(1)] = m.group(2) + f" (done rc={m.group(3)})"
        m = re.search(r"MODEL_DONE (\S+)", line)
        if m:
            cur[m.group(1)] = "ALL 14 DONE"
    return cur


def scan_cells() -> dict[str, dict[str, dict]]:
    data: dict[str, dict[str, dict]] = {}
    for model in MODELS:
        data[model] = {}
        for label, pack in CELLS:
            d = OUT_ROOT / model / f"{label}_{pack}_n{N}"
            agg_path = d / "aggregate.json"
            if not agg_path.is_file():
                trials = list(d.glob("trial_*.json")) if d.is_dir() else []
                data[model][label] = {
                    "status": "partial" if trials else "pending",
                    "trials": len(trials),
                    "rate": None,
                    "class": None,
                }
                continue
            agg = load_aggregate(agg_path)
            if not agg:
                data[model][label] = {"status": "bad_agg", "trials": N, "rate": None, "class": None}
                continue
            rate = present_rate(agg)
            if rate is None:
                data[model][label] = {"status": "done", "trials": N, "rate": None, "class": "?"}
            else:
                data[model][label] = {
                    "status": "done",
                    "trials": N,
                    "rate": rate,
                    "class": classify(rate),
                }
    return data


def scan_auth_errors() -> list[dict]:
    """Scan only this repro run's logs/work/report artifacts (not historical logs)."""
    hits = []
    auth_re = re.compile(r"(401|AuthenticationError|Unauthorized|invalid.?api.?key)", re.I)
    candidates: list[Path] = []
    # primary run logs
    for name in ("repro_14packs.log", "repro_14packs_nohup.out"):
        candidates.append(ROOT / "logs" / name)
    # work + report trees for this study
    for root in (ERR_GLOB_ROOT, OUT_ROOT):
        if not root.exists():
            continue
        for pth in root.rglob("*"):
            if not pth.is_file():
                continue
            name = pth.name.lower()
            if pth.suffix in {".err", ".log", ".out"} or name.endswith(".err") or "stderr" in name:
                candidates.append(pth)
    seen = set()
    for pth in candidates:
        try:
            rp = str(pth.resolve())
            if rp in seen:
                continue
            seen.add(rp)
            if not pth.is_file():
                continue
            if "MONITOR_14PACKS" in pth.name or "monitor_14packs" in pth.name:
                continue
            st = pth.stat()
            if st.st_size > 2_000_000 or st.st_size == 0:
                continue
            text = pth.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if auth_re.search(text):
            n = len(auth_re.findall(text))
            snip = ""
            for line in text.splitlines():
                if auth_re.search(line):
                    snip = line.strip()[:200]
                    break
            try:
                rel = str(pth.relative_to(ROOT))
            except Exception:
                rel = str(pth)
            hits.append({"path": rel, "n": n, "snip": snip, "mtime": st.st_mtime})
    return hits


def load_state() -> dict:
    if STATE_FILE.is_file():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {
        "seen_done_cells": [],
        "seen_model_done": [],
        "auth_alerted": False,
        "orch_dead_alerted": False,
        "positive_rate_logged": [],
        "last_auth_n": 0,
    }


def save_state(st: dict) -> None:
    STATE_FILE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def append_event(msg: str) -> None:
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    line = f"{now_str()} | {msg}\n"
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(line)
    print(f"EVENT: {msg}", flush=True)


def write_monitor(data, alive, pid, n_diag, current, auth_hits) -> None:
    lines = []
    lines.append("# MONITOR: 14 packs × all models")
    lines.append("")
    lines.append(f"**Updated:** {now_str()}")
    lines.append(f"**Orchestrator:** {'ALIVE pid=' + pid if alive else '**DEAD / EXITED**'}")
    lines.append(f"**Active diagnose processes:** {n_diag}")
    lines.append("")
    lines.append("## Per-model progress")
    lines.append("")
    lines.append("| Model | Agg complete | Progress | Current pack |")
    lines.append("|---|---:|---|---|")
    total_done = 0
    for model in MODELS:
        done = sum(1 for lab in LABELS if data[model][lab]["status"] == "done")
        total_done += done
        cur = current.get(model, "—")
        if done == 14:
            cur = "ALL 14 DONE"
        lines.append(f"| `{model}` | {done} | {done}/14 | {cur} |")
    lines.append("")
    lines.append(f"**Total cells complete:** {total_done} / {len(MODELS) * 14}")
    lines.append("")

    lines.append("## Completed cells — present_rate")
    lines.append("")
    lines.append("| Model | " + " | ".join(LABELS) + " |")
    lines.append("|---|" + "|".join(["---:" for _ in LABELS]) + "|")
    for model in MODELS:
        cells = []
        for lab in LABELS:
            c = data[model][lab]
            if c["status"] != "done" or c["rate"] is None:
                if c["status"] == "partial":
                    cells.append(f"…{c['trials']}/10")
                else:
                    cells.append("—")
            else:
                r = c["rate"]
                cl = c["class"]
                mark = ""
                if cl == "CONSISTENT":
                    mark = " **C**"
                elif cl == "MIXED":
                    mark = " **M**"
                elif cl == "RARE":
                    mark = " R"
                cells.append(f"{r:.2f}{mark}")
        lines.append(f"| `{model}` | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("Legend: **C**=CONSISTENT (≥0.9), **M**=MIXED (0.5–0.89), R=RARE (0.01–0.49), 0.00=NOT_REPRO")
    lines.append("")

    highlights = []
    for model in MODELS:
        for lab in LABELS:
            c = data[model][lab]
            if c.get("class") in ("CONSISTENT", "MIXED"):
                highlights.append(f"- `{model}` / **{lab}**: {c['rate']:.2f} → {c['class']}")
    lines.append("## MIXED / CONSISTENT highlights")
    lines.append("")
    if highlights:
        lines.extend(highlights)
    else:
        lines.append("_None yet_")
    lines.append("")

    lines.append("## AUTH failures")
    lines.append("")
    if auth_hits:
        for h in sorted(auth_hits, key=lambda x: -x["mtime"])[:30]:
            lines.append(f"- `{h['path']}` (n≈{h['n']}): {h['snip']}")
    else:
        lines.append("_No 401 / AuthenticationError detected in recent .err/.log files_")
    lines.append("")

    lines.append("## Log tail")
    lines.append("```")
    if LOG.is_file():
        tail = LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
        lines.extend(tail)
    else:
        lines.append("(no log yet)")
    lines.append("```")
    lines.append("")

    MONITOR_MD.parent.mkdir(parents=True, exist_ok=True)
    MONITOR_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(data) -> None:
    lines = []
    lines.append("# SUMMARY: 14 remaining packs × 10 trials × all models")
    lines.append("")
    lines.append(f"**Generated:** {now_str()}")
    lines.append("")
    lines.append("## present_rate matrix")
    lines.append("")
    lines.append("| Model | " + " | ".join(LABELS) + " |")
    lines.append("|---|" + "|".join(["---:" for _ in LABELS]) + "|")
    class_counts = {"CONSISTENT": 0, "MIXED": 0, "RARE": 0, "NOT_REPRO": 0}
    rows_detail = []
    for model in MODELS:
        cells = []
        for lab in LABELS:
            c = data[model][lab]
            if c["status"] != "done" or c["rate"] is None:
                cells.append("—")
            else:
                r = c["rate"]
                cl = c["class"]
                class_counts[cl] = class_counts.get(cl, 0) + 1
                tag = {"CONSISTENT": "C", "MIXED": "M", "RARE": "R", "NOT_REPRO": "N"}.get(cl, "?")
                cells.append(f"{r:.2f} {tag}")
                if cl in ("CONSISTENT", "MIXED", "RARE"):
                    rows_detail.append((cl, model, lab, r))
        lines.append(f"| `{model}` | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("Classification: C=CONSISTENT≥0.9, M=MIXED 0.5–0.89, R=RARE 0.01–0.49, N=NOT_REPRO 0.0")
    lines.append("")
    lines.append("## Classification counts")
    lines.append("")
    for k in ("CONSISTENT", "MIXED", "RARE", "NOT_REPRO"):
        lines.append(f"- **{k}**: {class_counts.get(k, 0)}")
    lines.append("")
    lines.append("## Highlighted cells (rate > 0)")
    lines.append("")
    order = {"CONSISTENT": 0, "MIXED": 1, "RARE": 2}
    rows_detail.sort(key=lambda x: (order.get(x[0], 9), -x[3], x[1], x[2]))
    if not rows_detail:
        lines.append("_All completed cells are NOT_REPRO (0.0) or incomplete_")
    else:
        for cl, model, lab, r in rows_detail:
            lines.append(f"- **{cl}** `{model}` / {lab}: {r:.2f}")
    lines.append("")
    auth = scan_auth_errors()
    lines.append("## AUTH failures")
    lines.append("")
    if auth:
        for h in auth[:40]:
            lines.append(f"- `{h['path']}`: {h['snip']}")
    else:
        lines.append("_None detected_")
    lines.append("")
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")


def process_events(data, alive, auth_hits, st: dict) -> dict:
    for model in MODELS:
        done = sum(1 for lab in LABELS if data[model][lab]["status"] == "done")
        if done == 14 and model not in st["seen_model_done"]:
            st["seen_model_done"].append(model)
            append_event(f"MODEL COMPLETE: {model} finished all 14 packs")
    for model in MODELS:
        for lab in LABELS:
            c = data[model][lab]
            key = f"{model}/{lab}"
            if c["status"] == "done" and c["rate"] is not None:
                if key not in st["seen_done_cells"]:
                    st["seen_done_cells"].append(key)
                    if c["rate"] > 0 and key not in st["positive_rate_logged"]:
                        st["positive_rate_logged"].append(key)
                        append_event(
                            f"PRESENT rate>0: {model} {lab} rate={c['rate']:.2f} class={c['class']}"
                        )
    if auth_hits:
        total_n = sum(h["n"] for h in auth_hits)
        if total_n >= 3 and not st.get("auth_alerted"):
            st["auth_alerted"] = True
            paths = ", ".join(h["path"] for h in auth_hits[:5])
            append_event(f"AUTH STORM: ~{total_n} auth matches across files e.g. {paths}")
        elif total_n >= 10:
            last = st.get("last_auth_n", 0)
            if total_n >= last + 10:
                st["last_auth_n"] = total_n
                append_event(f"AUTH STORM escalate: ~{total_n} auth matches")
    if not alive:
        total_done = sum(
            1 for m in MODELS for lab in LABELS if data[m][lab]["status"] == "done"
        )
        expected = len(MODELS) * 14
        if total_done < expected and not st.get("orch_dead_alerted"):
            st["orch_dead_alerted"] = True
            append_event(f"ORCHESTRATOR DEAD early: only {total_done}/{expected} aggregates complete")
    return st


def all_complete(data) -> bool:
    for m in MODELS:
        for lab in LABELS:
            if data[m][lab]["status"] != "done":
                return False
    return True


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    st = load_state()
    if not EVENTS.is_file() or EVENTS.stat().st_size == 0:
        append_event("MONITOR START: watching 14 packs × 13 models")

    print(f"Monitor running; poll every {POLL_SEC}s", flush=True)
    while True:
        alive, pid = orchestrator_alive()
        n_diag = count_diagnose()
        data = scan_cells()
        current = current_packs_from_log()
        auth_hits = scan_auth_errors()
        st = process_events(data, alive, auth_hits, st)
        write_monitor(data, alive, pid, n_diag, current, auth_hits)
        save_state(st)

        done_n = sum(1 for m in MODELS for lab in LABELS if data[m][lab]["status"] == "done")
        expected = len(MODELS) * 14
        print(
            f"{now_str()} alive={alive} diagnose={n_diag} cells={done_n}/{expected}",
            flush=True,
        )

        if all_complete(data):
            append_event(f"RUN COMPLETE: {done_n} aggregates present")
            write_summary(data)
            write_monitor(data, alive, pid, n_diag, current, auth_hits)
            print("All complete — summary written", flush=True)
            return 0

        if not alive:
            time.sleep(20)
            alive2, _ = orchestrator_alive()
            data = scan_cells()
            n_diag2 = count_diagnose()
            if not alive2 and n_diag2 == 0:
                done_n = sum(
                    1 for m in MODELS for lab in LABELS if data[m][lab]["status"] == "done"
                )
                if all_complete(data):
                    append_event("RUN COMPLETE after orch exit")
                    write_summary(data)
                    return 0
                if not st.get("orch_dead_alerted"):
                    st["orch_dead_alerted"] = True
                    append_event(
                        f"ORCHESTRATOR EXITED incomplete: {done_n}/{expected} aggregates"
                    )
                write_summary(data)
                write_monitor(data, False, "", 0, current_packs_from_log(), scan_auth_errors())
                save_state(st)
                print("Orchestrator exited incomplete — summary written", flush=True)
                return 1

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
