"""Harbor run layout management for reports/harbor_runs/{job_id}/ .

Per global constraints + task-1b-brief:
  reports/harbor_runs/{job_id}/
    meta.json
    reward.json                 # optional aggregate
    rewards/{pack}__t{i}.json
    trajectories/{pack}__t{i}/  # litellm.jsonl, conversation.json, traces.json, scores.json, meta.json
    logs/                       # raw Harbor logs if any
    docker_cleanup.json
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(name: str) -> str:
    # simple safe for pack__tN
    return "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in str(name))


def harbor_run_dir(base: Path, job_id: str) -> Path:
    """Return Path for the job run dir. In usage: base=reports_dir or reports/harbor_runs.

    For tests, often called with tmp_path so job sits directly under (caller controls).
    Real usage will typically pass reports_dir; layout docs specify harbor_runs/ subdir.
    """
    base = Path(base)
    jid = _safe_name(job_id)[:64] or "job"
    # Do not force /harbor_runs here to keep tests using tmp as sandbox happy;
    # callers that want strict reports/harbor_runs pass base=reports_dir / "harbor_runs"
    # or we can detect. For now keep simple and match brief/tests.
    return base / jid


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def init_run(
    base: Path,
    job_id: str,
    *,
    model: str = "",
    packs: list[str] | None = None,
    **extra_meta: Any,
) -> Path:
    """Initialize harbor_runs/{job_id} layout under base (or base as harbor_runs root).

    Writes meta.json. Returns the job root Path.
    """
    root = harbor_run_dir(base, job_id)
    root.mkdir(parents=True, exist_ok=True)

    meta = {
        "job_id": job_id,
        "model": model,
        "packs": packs or [],
        "started_at": _now_iso(),
        "schema": "harbor_runs/v1",
        **extra_meta,
    }
    _write_json(root / "meta.json", meta)

    # ensure subdirs exist early (optional)
    (root / "rewards").mkdir(exist_ok=True)
    (root / "trajectories").mkdir(exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)

    return root


def persist_reward(
    root: Path, pack_id: str, trial_index: int, reward: dict[str, Any]
) -> None:
    """Write per-trial Harbor reward under rewards/{pack}__t{i}.json .

    Also writes top-level reward.json if this is the aggregate or first; but per brief,
    optional aggregate at root.
    """
    root = Path(root)
    safe = f"{_safe_name(pack_id)}__t{int(trial_index)}"
    rew_dir = root / "rewards"
    rew_dir.mkdir(parents=True, exist_ok=True)
    path = rew_dir / f"{safe}.json"
    _write_json(path, reward)

    # convenience: if caller passes aggregate-like, or always update a top reward.json?
    # per layout "reward.json # optional aggregate" -- only write if not present or if primary key present at top
    top = root / "reward.json"
    if not top.exists() or "primary_pass" in reward:
        # write this one as top for simple cases; real aggregate may be done by runner
        _write_json(top, reward)


def persist_trajectory(
    root: Path, pack_id: str, trial_index: int, src_dir: Path
) -> None:
    """Copy trajectory artifacts into trajectories/{pack}__t{i}/ .

    Expected files: litellm.jsonl, conversation.json, traces.json, scores.json, meta.json
    If src_dir missing some, still create dir and copy what exists.
    """
    root = Path(root)
    safe = f"{_safe_name(pack_id)}__t{int(trial_index)}"
    tdir = root / "trajectories" / safe
    tdir.mkdir(parents=True, exist_ok=True)

    src = Path(src_dir)
    for fname in ("litellm.jsonl", "conversation.json", "traces.json", "scores.json", "meta.json"):
        sp = src / fname
        dp = tdir / fname
        if sp.is_file():
            shutil.copy2(sp, dp)
        else:
            # ensure placeholder for required shape
            if not dp.exists():
                _write_json(dp, [] if fname.endswith(".json") and fname != "meta.json" else {} if fname == "meta.json" else "")


def persist_logs(root: Path, src_logs_dir: Path | None = None) -> None:
    """Copy raw logs (if any) into logs/ .

    src_logs_dir: dir whose contents are copied recursively.
    """
    root = Path(root)
    logdir = root / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    if src_logs_dir is None:
        return
    src = Path(src_logs_dir)
    if not src.exists():
        return
    if src.is_file():
        shutil.copy2(src, logdir / src.name)
        return
    # copy tree contents
    for p in src.rglob("*"):
        if p.is_file():
            rel = p.relative_to(src)
            (logdir / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, logdir / rel)


def finalize_meta(root: Path, updates: dict[str, Any]) -> None:
    """Merge updates into meta.json (idempotent, last write wins for keys)."""
    root = Path(root)
    meta_path = root / "meta.json"
    meta: dict[str, Any] = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    meta.update(updates or {})
    if "ended_at" not in meta and "status" in (updates or {}):
        meta.setdefault("ended_at", _now_iso())
    _write_json(meta_path, meta)
