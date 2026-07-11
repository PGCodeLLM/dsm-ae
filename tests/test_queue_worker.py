"""Worker e2e: claim → diagnose(mock) → artifacts → status."""
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from dsm_ae.cli import app
from dsm_ae.queue.models import JobStatus
from dsm_ae.queue.store import JobStore
from dsm_ae.queue.worker import run_loop, run_one

runner = CliRunner()


def test_run_one_mock(tmp_path: Path):
    db = tmp_path / "q.db"
    reports = tmp_path / "reports"
    store = JobStore(db)
    jid = store.enqueue(model="mock/well_attuned", packs=["hello_metacog"], k=2)
    ok = run_one(store, worker_id="t", reports_dir=reports, models_yaml=None)
    assert ok is True
    job = store.get(jid)
    assert job is not None
    assert job.status.value == "succeeded"
    assert job.out_json is not None
    assert Path(job.out_json).is_file()
    assert job.out_md is not None
    assert Path(job.out_md).is_file()
    # idle when empty
    assert run_one(store, worker_id="t", reports_dir=reports, models_yaml=None) is None


def test_run_one_failure_marks_failed(tmp_path: Path):
    db = tmp_path / "q.db"
    reports = tmp_path / "reports"
    store = JobStore(db)
    jid = store.enqueue(model="mock/well_attuned", packs=["no_such_pack_xyz"], k=1)
    ok = run_one(store, worker_id="t", reports_dir=reports, models_yaml=None)
    assert ok is False
    job = store.get(jid)
    assert job is not None
    assert job.status == JobStatus.FAILED
    assert job.error


def test_run_loop_once_drains_queue(tmp_path: Path):
    db = tmp_path / "q.db"
    reports = tmp_path / "reports"
    store = JobStore(db)
    store.enqueue(model="mock/well_attuned", packs=["hello_metacog"], k=1)
    store.enqueue(model="mock/well_attuned", packs=["hello_metacog"], k=1)
    run_loop(
        store,
        worker_id="loop",
        reports_dir=reports,
        models_yaml=None,
        once=True,
        poll_s=0.01,
        rebuild_html=False,
    )
    jobs = store.list_jobs()
    assert len(jobs) == 2
    assert all(j.status == JobStatus.SUCCEEDED for j in jobs)


def test_worker_cli_once(tmp_path: Path):
    db = tmp_path / "q.db"
    reports = tmp_path / "reports"
    store = JobStore(db)
    jid = store.enqueue(model="mock/well_attuned", packs=["hello_metacog"], k=1)
    result = runner.invoke(
        app,
        [
            "worker",
            "--db",
            str(db),
            "--reports-dir",
            str(reports),
            "--once",
            "--worker-id",
            "cli-w",
            "--no-rebuild-html",
        ],
    )
    assert result.exit_code == 0, result.output
    job = store.get(jid)
    assert job is not None
    assert job.status == JobStatus.SUCCEEDED
    assert job.worker_id == "cli-w"
