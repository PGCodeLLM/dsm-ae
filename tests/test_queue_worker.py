"""Worker e2e: claim → diagnose(mock) → artifacts → status."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


def test_run_one_respects_custom_out_paths(tmp_path: Path):
    db = tmp_path / "q.db"
    reports = tmp_path / "reports"
    custom_md = tmp_path / "custom" / "out.md"
    custom_json = tmp_path / "custom" / "out.json"
    store = JobStore(db)
    jid = store.enqueue(
        model="mock/well_attuned",
        packs=["hello_metacog"],
        k=1,
        out_md=str(custom_md),
        out_json=str(custom_json),
    )
    ok = run_one(store, worker_id="t", reports_dir=reports, models_yaml=None)
    assert ok is True
    job = store.get(jid)
    assert job is not None
    assert job.status == JobStatus.SUCCEEDED
    assert Path(job.out_md) == custom_md
    assert Path(job.out_json) == custom_json
    assert custom_md.is_file()
    assert custom_json.is_file()


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


def test_run_loop_reclaims_stale_running(tmp_path: Path):
    """Worker start marks long-running jobs failed via requeue_stale."""
    db = tmp_path / "q.db"
    reports = tmp_path / "reports"
    store = JobStore(db)
    jid = store.enqueue(model="mock/well_attuned", packs=["hello_metacog"], k=1)
    claimed = store.claim_next(worker_id="dead-worker")
    assert claimed is not None
    old = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    store._conn.execute(
        "UPDATE eval_jobs SET started_at=? WHERE id=?",
        (old, jid),
    )
    store._conn.commit()

    reclaimed = run_loop(
        store,
        worker_id="new-worker",
        reports_dir=reports,
        models_yaml=None,
        once=True,
        poll_s=0.01,
        rebuild_html=False,
        stale_seconds=3600,
    )
    assert reclaimed == 1
    job = store.get(jid)
    assert job is not None
    assert job.status == JobStatus.FAILED
    assert job.error is not None
    assert "stale" in job.error.lower()


def test_run_loop_stale_seconds_zero_skips_reclaim(tmp_path: Path):
    db = tmp_path / "q.db"
    reports = tmp_path / "reports"
    store = JobStore(db)
    jid = store.enqueue(model="mock/well_attuned", packs=["hello_metacog"], k=1)
    store.claim_next(worker_id="dead-worker")
    old = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    store._conn.execute(
        "UPDATE eval_jobs SET started_at=? WHERE id=?",
        (old, jid),
    )
    store._conn.commit()

    reclaimed = run_loop(
        store,
        worker_id="new-worker",
        reports_dir=reports,
        models_yaml=None,
        once=True,
        poll_s=0.01,
        rebuild_html=False,
        stale_seconds=0,
    )
    assert reclaimed == 0
    assert store.get(jid).status == JobStatus.RUNNING


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


def test_worker_cli_reclaims_stale(tmp_path: Path):
    db = tmp_path / "q.db"
    reports = tmp_path / "reports"
    store = JobStore(db)
    jid = store.enqueue(model="mock/well_attuned", packs=["hello_metacog"], k=1)
    store.claim_next(worker_id="dead")
    old = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    store._conn.execute(
        "UPDATE eval_jobs SET started_at=? WHERE id=?",
        (old, jid),
    )
    store._conn.commit()

    result = runner.invoke(
        app,
        [
            "worker",
            "--db",
            str(db),
            "--reports-dir",
            str(reports),
            "--once",
            "--stale-seconds",
            "3600",
            "--no-rebuild-html",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "reclaimed" in result.output.lower() or "stale" in result.output.lower()
    job = store.get(jid)
    assert job is not None
    assert job.status == JobStatus.FAILED
