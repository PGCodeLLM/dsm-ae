#!/usr/bin/env python3
"""Monitor gpt-5.6-sol tier2 calibration until done."""
from __future__ import annotations
import json, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs/tier2"
OUT = ROOT / "reports/tier2"
WORK = ROOT / "reports/work/tier2_sol"
POLL = 30

def now():
    return datetime.now(timezone.utc).isoformat()

def pgrep(pat: str) -> bool:
    r = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())

def main():
    print(f"TIER2_MONITOR_START at={now()}", flush=True)
    last = ""
    while True:
        cal = pgrep("run_tier2_sol_calibration") or pgrep("dsm-ae diagnose -m gpt-5.6-sol")
        # progress via workdir
        ckpts = len(list(WORK.rglob(".dsm_ae_ckpt/*.json"))) if WORK.is_dir() else 0
        lit = len(list(WORK.rglob("litellm.jsonl"))) if WORK.is_dir() else 0
        outs = sorted(OUT.glob("*.json")) if OUT.is_dir() else []
        nohup = ROOT / "logs/tier2/sol_calibration_nohup.out"
        tail = ""
        if nohup.is_file():
            lines = nohup.read_text(errors="replace").strip().splitlines()
            tail = "\n".join(lines[-8:])
        key = (cal, ckpts, lit, tuple(p.name for p in outs), tail)
        if str(key) != last:
            print(f"--- {now()} diagnose_or_script={cal} ckpts={ckpts} litellm={lit} outs={[p.name for p in outs]} ---", flush=True)
            if tail:
                for ln in tail.splitlines():
                    print(f"  LOG {ln}", flush=True)
            last = str(key)
        # done: script gone and output json exists
        cal_json = list(OUT.glob("*tier2-cal.json")) + list(OUT.glob("*sol*.json"))
        if not cal and cal_json:
            print(f"TIER2_MONITOR_DONE at={now()} files={[p.name for p in cal_json]}", flush=True)
            for p in cal_json:
                try:
                    d = json.loads(p.read_text())
                    gates = d.get("gates") or []
                    tiers = [g for g in gates if "erosion" in str(g.get("metric_id","")) or "verbosity" in str(g.get("metric_id",""))]
                    print(f"  {p.name}: findings_present={sum(1 for f in d.get('findings') or [] if f.get('present'))}", flush=True)
                    for g in tiers[:12]:
                        print(f"    {g.get('metric_id')}: {g.get('status')} pr={g.get('pass_rate')} disorder={g.get('disorder')}", flush=True)
                except Exception as e:
                    print(f"  parse {p}: {e}", flush=True)
            break
        if not cal and not cal_json:
            # wait a bit for late write
            time.sleep(POLL)
            if not pgrep("run_tier2_sol_calibration") and not pgrep("dsm-ae diagnose -m gpt-5.6-sol"):
                still = list(OUT.glob("*.json")) if OUT.is_dir() else []
                if still:
                    continue
                print(f"TIER2_MONITOR_WARN process gone no output at={now()}", flush=True)
                if nohup.is_file():
                    print(nohup.read_text(errors="replace")[-1500:], flush=True)
                break
            continue
        time.sleep(POLL)
    print("TIER2_MONITOR_EXIT", flush=True)

if __name__ == "__main__":
    main()
