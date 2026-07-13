#!/usr/bin/env python3
"""Watch tier23-missing queue jobs until all terminal; alert on fail / missing trajectories."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "queue.db"
LABEL_PREFIX = "tier23%"
POLL = 30
STUCK_S = 900  # 15 min no progress while running
TERMINAL = {"succeeded", "failed", "cancelled"}


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso() -> str:
    return now().isoformat()


def load_jobs() -> list[dict]:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM eval_jobs
           WHERE label LIKE ?
           ORDER BY created_at""",
        (LABEL_PREFIX,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def progress(job: dict) -> dict | None:
    pp = job.get("progress_path")
    if not pp or not Path(pp).is_file():
        return None
    try:
        return json.loads(Path(pp).read_text(encoding="utf-8"))
    except Exception:
        return None


def work_dir(job: dict) -> Path:
    if job.get("work_dir"):
        return Path(job["work_dir"])
    return ROOT / "reports" / "work" / job["id"][:8]


def traj_stats(wd: Path) -> dict:
    if not wd.is_dir():
        return {"litellm": 0, "ckpts": 0, "convs": 0, "bytes": 0}
    lit = list(wd.rglob("litellm.jsonl"))
    ckpt = list((wd / ".dsm_ae_ckpt").glob("*.json")) if (wd / ".dsm_ae_ckpt").is_dir() else []
    conv = list(wd.rglob("conversation.json"))
    nbytes = sum(p.stat().st_size for p in lit if p.is_file())
    return {
        "litellm": len(lit),
        "ckpts": len(ckpt),
        "convs": len(conv),
        "bytes": nbytes,
    }


def serve_alive() -> bool:
    r = subprocess.run(
        ["pgrep", "-f", "dsm-ae serve-queue"],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0 and bool(r.stdout.strip())


def main() -> None:
    print(f"TIER23_MONITOR_START at={iso()} label={LABEL_PREFIX!r} stuck_after={STUCK_S}s", flush=True)
    last_key: dict[str, tuple] = {}
    announced_fail: set[str] = set()
    announced_done: set[str] = set()
    stuck_notify: dict[str, float] = {}

    while True:
        jobs = load_jobs()
        if not jobs:
            print("TIER23_MONITOR_ERROR no jobs with label tier23%", flush=True)
            time.sleep(POLL)
            continue

        alive = serve_alive()
        all_terminal = True
        n_ok = n_fail = n_run = n_q = 0

        for job in jobs:
            jid = job["id"]
            short = jid[:8]
            status = job["status"]
            model = job["model"]
            prog = progress(job)
            pct = prog.get("percent") if prog else None
            msg = (prog.get("message") if prog else None) or ""
            updated = prog.get("updated_at") if prog else None
            age = None
            if updated:
                try:
                    u = datetime.fromisoformat(updated)
                    if u.tzinfo is None:
                        u = u.replace(tzinfo=timezone.utc)
                    age = (now() - u).total_seconds()
                except Exception:
                    pass

            wd = work_dir(job)
            stats = traj_stats(wd)
            key = (status, pct, msg, updated, stats["litellm"], stats["ckpts"], stats["bytes"])

            if status not in TERMINAL:
                all_terminal = False
            if status == "running":
                n_run += 1
            elif status == "queued":
                n_q += 1
            elif status == "succeeded":
                n_ok += 1
            elif status == "failed":
                n_fail += 1

            if last_key.get(short) != key:
                print(
                    f"PROGRESS id={short} model={model} status={status} "
                    f"pct={pct} age_s={None if age is None else int(age)} "
                    f"msg={msg!r} litellm={stats['litellm']} ckpts={stats['ckpts']} "
                    f"traj_bytes={stats['bytes']} serve={alive}",
                    flush=True,
                )
                last_key[short] = key

            # Failure notification (once per job)
            if status == "failed" and short not in announced_fail:
                err = (job.get("error") or "")[:500]
                print(
                    f"MONITOR_FAIL id={short} model={model} error={err!r} "
                    f"work={wd} litellm={stats['litellm']} ckpts={stats['ckpts']}",
                    flush=True,
                )
                announced_fail.add(short)

            # Success: require trajectories
            if status == "succeeded" and short not in announced_done:
                ok_traj = stats["litellm"] > 0 and stats["bytes"] > 0 and stats["ckpts"] > 0
                if ok_traj:
                    print(
                        f"MONITOR_OK id={short} model={model} "
                        f"litellm={stats['litellm']} ckpts={stats['ckpts']} "
                        f"convs={stats['convs']} bytes={stats['bytes']} work={wd}",
                        flush=True,
                    )
                else:
                    print(
                        f"MONITOR_FAIL id={short} model={model} "
                        f"reason=missing_trajectories "
                        f"litellm={stats['litellm']} ckpts={stats['ckpts']} "
                        f"convs={stats['convs']} bytes={stats['bytes']} work={wd} "
                        f"(job marked succeeded but LiteLLM/ckpt artifacts incomplete)",
                        flush=True,
                    )
                    announced_fail.add(short)
                announced_done.add(short)

            # Stuck detection
            if status == "running" and age is not None and age >= STUCK_S:
                if time.time() - stuck_notify.get(short, 0) >= STUCK_S:
                    print(
                        f"MONITOR_STUCK id={short} model={model} pct={pct} "
                        f"no_progress_for_s={int(age)} msg={msg!r} serve={alive}",
                        flush=True,
                    )
                    stuck_notify[short] = time.time()

            if status == "running" and not alive:
                if time.time() - stuck_notify.get(short + "_dead", 0) >= 60:
                    print(
                        f"MONITOR_STUCK id={short} model={model} "
                        f"serve-queue NOT RUNNING while job running",
                        flush=True,
                    )
                    stuck_notify[short + "_dead"] = time.time()

        if all_terminal:
            print(
                f"MONITOR_ALL_DONE ok={n_ok} failed={n_fail} total={len(jobs)} at={iso()}",
                flush=True,
            )
            # final trajectory audit
            missing = []
            for job in jobs:
                if job["status"] != "succeeded":
                    continue
                st = traj_stats(work_dir(job))
                if st["litellm"] == 0 or st["ckpts"] == 0:
                    missing.append((job["id"][:8], job["model"], st))
            if missing:
                print(f"MONITOR_FAIL trajectory_audit_missing={missing}", flush=True)
            else:
                print("MONITOR_OK all_succeeded_jobs_have_litellm_and_ckpts", flush=True)
            break

        time.sleep(POLL)

    print("TIER23_MONITOR_EXIT", flush=True)


if __name__ == "__main__":
    main()
