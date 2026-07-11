"""Claim eval jobs, run diagnose, write reports, rebuild HTML matrix."""
from __future__ import annotations

import json
import socket
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

from dsm_ae.diagnose import diagnose
from dsm_ae.queue.paths import job_report_paths
from dsm_ae.queue.progress import (
    progress_path_for,
    read_secret,
    write_progress,
)
from dsm_ae.queue.store import JobStore
from dsm_ae.report import render_markdown


def default_worker_id() -> str:
    return f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


def run_one(
    store: JobStore,
    *,
    worker_id: str,
    reports_dir: Path,
    models_yaml: Path | None,
    rebuild_html: bool = True,
    matrix_out: Path | None = None,
) -> bool | None:
    """Claim and run at most one job. True=ran ok, False=ran fail, None=idle.

    On failure the job is marked failed (no auto-retry). ``max_attempts`` is
    reserved for a future auto-retry policy; use ``queue retry`` to re-queue
    manually. Prefer job.out_md / job.out_json when set, else default paths.
    Writes a progress JSON file under reports/queue/progress/ for the UI.
    """
    job = store.claim_next(worker_id)
    if job is None:
        return None
    reports_dir = Path(reports_dir)
    default_md, default_json = job_report_paths(
        reports_dir, job.id, job.model, job.label
    )
    md_path = Path(job.out_md) if job.out_md else default_md
    json_path = Path(job.out_json) if job.out_json else default_json
    work = Path(job.work_dir) if job.work_dir else reports_dir / "work" / job.id[:8]
    prog_path = (
        Path(job.progress_path)
        if job.progress_path
        else progress_path_for(reports_dir, job.id)
    )
    store.update_paths(job.id, progress_path=str(prog_path))

    def on_progress(payload: dict[str, Any]) -> None:
        write_progress(
            prog_path,
            {
                "job_id": job.id,
                "model": job.model,
                **payload,
            },
        )

    api_key = None
    secret = read_secret(job.secret_path)
    if secret:
        api_key = secret.get("api_key") or None
        if api_key == "":
            api_key = None

    write_progress(
        prog_path,
        {
            "job_id": job.id,
            "model": job.model,
            "phase": "claimed",
            "status": "running",
            "done": 0,
            "total": 0,
            "message": f"Claimed by {worker_id}",
        },
    )
    try:
        report = diagnose(
            model=job.model,
            packs=job.packs,
            k=job.k,
            concurrency=job.concurrency,
            rpm=job.rpm,
            scaffold=job.scaffold,
            models_yaml=models_yaml,
            api_base=job.api_base,
            api_key=api_key,
            work_dir=work,
            on_progress=on_progress,
            client_extra=job.extra,
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(report), encoding="utf-8")
        payload = report.model_dump(mode="json")
        if len(payload.get("traces", [])) > 20:
            payload["traces"] = f"<{len(report.traces)} traces omitted>"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        store.mark_succeeded(job.id, out_md=str(md_path), out_json=str(json_path))
        write_progress(
            prog_path,
            {
                "job_id": job.id,
                "model": job.model,
                "phase": "done",
                "status": "succeeded",
                "done": 1,
                "total": 1,
                "percent": 100.0,
                "message": "Report written",
                "out_json": str(json_path),
            },
        )
        if rebuild_html:
            _rebuild_matrix(reports_dir, matrix_out)
        return True
    except Exception:
        err = traceback.format_exc()
        store.mark_failed(job.id, err)
        write_progress(
            prog_path,
            {
                "job_id": job.id,
                "model": job.model,
                "phase": "failed",
                "status": "failed",
                "message": err.splitlines()[-1] if err else "failed",
                "error": err[:2000],
            },
        )
        return False


def run_loop(
    store: JobStore,
    *,
    worker_id: str,
    reports_dir: Path,
    models_yaml: Path | None,
    once: bool = False,
    poll_s: float = 2.0,
    rebuild_html: bool = True,
    matrix_out: Path | None = None,
    stale_seconds: float = 3600,
) -> int:
    """Process jobs serially. With once=True, drain until idle then return.

    Before claiming, marks long-running jobs failed via ``requeue_stale`` so a
    crashed worker's claims can be retried with ``queue retry``. Pass
    ``stale_seconds=0`` to skip reclaim. Returns the number of stale jobs
    reclaimed at start.
    """
    reclaimed = 0
    if stale_seconds > 0:
        reclaimed = store.requeue_stale(stale_seconds=stale_seconds)
        if reclaimed:
            print(
                f"Reclaimed {reclaimed} stale running job(s) "
                f"(stale_seconds={stale_seconds:g})",
                file=sys.stderr,
            )
    while True:
        result = run_one(
            store,
            worker_id=worker_id,
            reports_dir=reports_dir,
            models_yaml=models_yaml,
            rebuild_html=rebuild_html,
            matrix_out=matrix_out,
        )
        if result is None:
            if once:
                return reclaimed
            time.sleep(poll_s)
    return reclaimed  # pragma: no cover — infinite poll loop


def _rebuild_matrix(reports_dir: Path, matrix_out: Path | None) -> None:
    """Rebuild multi-model HTML matrix from diagnosis JSON under reports_dir.

    Failures are logged only — they must not fail an already-succeeded job.
    """
    reports_dir = Path(reports_dir)
    out = Path(matrix_out) if matrix_out else reports_dir / "dsm-ae-matrix.html"
    try:
        script = Path.cwd() / "scripts" / "json_to_html_report.py"
        if not script.exists():
            script = (
                Path(__file__).resolve().parents[3] / "scripts" / "json_to_html_report.py"
            )
        sys.path.insert(0, str(script.parent))
        from json_to_html_report import main as html_main  # type: ignore

        args = [str(reports_dir), "-o", str(out), "--include-mock"]
        rc = html_main(args)
        if rc != 0:
            print(
                f"HTML matrix rebuild returned {rc} (out={out})",
                file=sys.stderr,
            )
        else:
            print(f"Rebuilt matrix → {out}")
    except Exception as e:
        print(f"HTML matrix rebuild failed (non-fatal): {e}", file=sys.stderr)
