"""Claim eval jobs, run diagnose, write reports, rebuild HTML matrix."""
from __future__ import annotations

import json
import socket
import sys
import time
import traceback
import uuid
from pathlib import Path

from dsm_ae.diagnose import diagnose
from dsm_ae.queue.paths import job_report_paths
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
    """Claim and run at most one job. True=ran ok, False=ran fail, None=idle."""
    job = store.claim_next(worker_id)
    if job is None:
        return None
    reports_dir = Path(reports_dir)
    md_path, json_path = job_report_paths(
        reports_dir, job.id, job.model, job.label
    )
    work = Path(job.work_dir) if job.work_dir else reports_dir / "work" / job.id[:8]
    try:
        report = diagnose(
            model=job.model,
            packs=job.packs,
            k=job.k,
            concurrency=job.concurrency,
            rpm=job.rpm,
            scaffold=job.scaffold,
            models_yaml=models_yaml,
            work_dir=work,
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(report), encoding="utf-8")
        payload = report.model_dump(mode="json")
        if len(payload.get("traces", [])) > 20:
            payload["traces"] = f"<{len(report.traces)} traces omitted>"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        store.mark_succeeded(job.id, out_md=str(md_path), out_json=str(json_path))
        if rebuild_html:
            _rebuild_matrix(reports_dir, matrix_out)
        return True
    except Exception:
        store.mark_failed(job.id, traceback.format_exc())
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
) -> None:
    """Process jobs serially. With once=True, drain until idle then return."""
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
                return
            time.sleep(poll_s)


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
