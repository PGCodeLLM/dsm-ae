#!/usr/bin/env python3
"""Monitor gpt-5.6-luna treatment trial until all arms finish. Never kills processes."""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs/treatment/luna_trial.log"
OUT = ROOT / "reports/treatment"
WORK = ROOT / "reports/work/treatment_luna"
ARMS = ("baseline", "prompt_reminder", "skill_scaffold", "expert_oversight")
POLL = 30


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def arm_progress(arm: str) -> str:
    w = WORK / arm
    ck = len(list((w / ".dsm_ae_ckpt").glob("*.json"))) if (w / ".dsm_ae_ckpt").is_dir() else 0
    lit = len(list((w / "trajectories").rglob("litellm.jsonl"))) if (w / "trajectories").is_dir() else 0
    packs = [p.name for p in w.iterdir() if p.is_dir() and p.name not in {".dsm_ae_ckpt", "trajectories"}] if w.is_dir() else []
    done = (OUT / f"gpt-5.6-luna-{arm}.json").is_file()
    return f"done_json={done} ckpts={ck}/18 litellm={lit} packs={packs[-4:] if packs else []}"


def diagnose_alive() -> bool:
    r = subprocess.run(
        ["pgrep", "-f", "dsm-ae diagnose -m gpt-5.6-luna"],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0 and bool(r.stdout.strip())


def trial_script_alive() -> bool:
    r = subprocess.run(
        ["pgrep", "-f", "run_treatment_luna_trial"],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0 and bool(r.stdout.strip())


def main() -> None:
    print(f"TREAT_MONITOR_START at={now()}", flush=True)
    print(f"  trial_log={LOG}", flush=True)
    print(f"  monitor_log={ROOT / 'logs/treatment/monitor.log'}", flush=True)
    print(f"  outputs={OUT}", flush=True)
    last_key = None
    while True:
        alive = diagnose_alive()
        script = trial_script_alive()
        trial_txt = LOG.read_text(encoding="utf-8", errors="replace") if LOG.is_file() else ""
        arms = {a: arm_progress(a) for a in ARMS}
        key = (alive, script, trial_txt, tuple(arms.items()))
        if key != last_key:
            print(f"--- {now()} diagnose={alive} script={script} ---", flush=True)
            for line in trial_txt.strip().splitlines()[-8:]:
                print(f"  TRIAL {line}", flush=True)
            for a, s in arms.items():
                print(f"  ARM {a}: {s}", flush=True)
            last_key = key

        if "TREATMENT_TRIAL_DONE" in trial_txt:
            print(f"TREAT_MONITOR_DONE at={now()}", flush=True)
            summary = OUT / "SUMMARY.md"
            if summary.is_file():
                print(summary.read_text(encoding="utf-8"), flush=True)
            break

        if not script and not alive and "TREATMENT_TRIAL_DONE" not in trial_txt:
            # finished arms may have crashed
            print(f"TREAT_MONITOR_WARN trial process gone without DONE at={now()}", flush=True)
            for a in ARMS:
                print(f"  ARM {a}: {arm_progress(a)}", flush=True)
            # wait a bit more then exit if still dead
            time.sleep(60)
            if not trial_script_alive() and not diagnose_alive():
                print("TREAT_MONITOR_EXIT orphaned", flush=True)
                break
            continue

        time.sleep(POLL)


if __name__ == "__main__":
    main()
