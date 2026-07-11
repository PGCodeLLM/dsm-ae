# Evaluation Queue Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a durable SQLite-backed evaluation queue so models can be enqueued for diagnosis and compared via the existing HTML matrix, instead of offline shell batches driven by hard-coded model lists.

**Architecture:** Jobs (model + packs + k + limits) live in SQLite; credentials stay in `models.yaml`. A `dsm-ae worker` claims jobs, calls existing `diagnose()`, writes report JSON/MD, rebuilds the matrix HTML. Optional thin HTTP status/UI later.

**Tech Stack:** Python 3.11+, stdlib `sqlite3`, existing typer CLI, pydantic models, pytest; optional FastAPI only in Task 5.

**Spec:** `docs/superpowers/specs/2026-07-10-eval-queue-design.md`

## Global Constraints

- Do not store API keys in SQLite or job payloads
- Reuse `dsm_ae.diagnose.diagnose` — no second engine
- Default worker concurrency = 1 job; pack×trial concurrency remains job field
- Keep DiagnosisReport JSON schema stable for `scripts/json_to_html_report.py`
- Offline mock models (`mock/*`) must work without `models.yaml`
- `work/` and `models.yaml` remain gitignored

---

## File structure

| Path | Role |
|------|------|
| `src/dsm_ae/queue/__init__.py` | Package export |
| `src/dsm_ae/queue/models.py` | Job dataclasses / status enum |
| `src/dsm_ae/queue/store.py` | SQLite schema + enqueue/claim/list/cancel |
| `src/dsm_ae/queue/worker.py` | Claim loop → diagnose → artifacts → HTML |
| `src/dsm_ae/queue/paths.py` | Default DB path, report path helpers |
| `src/dsm_ae/cli.py` | `queue` sub-app + `worker` command |
| `tests/test_queue_store.py` | Store unit tests |
| `tests/test_queue_worker.py` | Worker e2e with mock model |
| `docs/superpowers/specs/2026-07-10-eval-queue-design.md` | Design (already written) |

---

### Task 1: Job model + SQLite store

**Files:**
- Create: `src/dsm_ae/queue/__init__.py`
- Create: `src/dsm_ae/queue/models.py`
- Create: `src/dsm_ae/queue/paths.py`
- Create: `src/dsm_ae/queue/store.py`
- Test: `tests/test_queue_store.py`

**Interfaces:**
- Produces: `JobStore.enqueue`, `claim_next`, `list_jobs`, `get`, `cancel`, `mark_succeeded`, `mark_failed`, `requeue_stale`

- [ ] **Step 1: Write failing tests for enqueue + claim**

```python
# tests/test_queue_store.py
from pathlib import Path
from dsm_ae.queue.store import JobStore
from dsm_ae.queue.models import JobStatus

def test_enqueue_and_claim(tmp_path: Path):
    store = JobStore(tmp_path / "q.db")
    jid = store.enqueue(model="mock/well_attuned", packs=["hello_metacog"], k=2)
    job = store.claim_next(worker_id="w1")
    assert job is not None
    assert job.id == jid
    assert job.status == JobStatus.RUNNING
    assert store.claim_next(worker_id="w2") is None  # only one queued
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/arcyleung/Projects/grok_trace_analysis/dsm-ae
pytest tests/test_queue_store.py::test_enqueue_and_claim -v
```

Expected: FAIL import or missing module

- [ ] **Step 3: Implement models + store**

```python
# src/dsm_ae/queue/models.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class EvalJob:
    id: str
    model: str
    packs: list[str] | None
    k: int
    concurrency: int
    rpm: float | None
    scaffold: str
    priority: int
    status: JobStatus
    error: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    worker_id: str | None
    attempt: int
    max_attempts: int
    out_md: str | None
    out_json: str | None
    work_dir: str | None
    label: str | None
```

```python
# src/dsm_ae/queue/paths.py
from pathlib import Path

def default_db_path(root: Path | None = None) -> Path:
    root = root or Path.cwd()
    return root / "data" / "queue.db"

def job_report_paths(reports_dir: Path, job_id: str, model: str, label: str | None):
    safe = (label or model).replace("/", "_").replace(".", "_")
    short = job_id[:8]
    base = reports_dir / "queue"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{safe}-{short}.md", base / f"{safe}-{short}.json"
```

```python
# src/dsm_ae/queue/store.py
"""SQLite-backed eval job store. Uses BEGIN IMMEDIATE for claim."""
from __future__ import annotations
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dsm_ae.queue.models import EvalJob, JobStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS eval_jobs (
  id TEXT PRIMARY KEY,
  model TEXT NOT NULL,
  packs_json TEXT,
  k INTEGER NOT NULL,
  concurrency INTEGER NOT NULL DEFAULT 1,
  rpm REAL,
  scaffold TEXT NOT NULL DEFAULT 'raw',
  priority INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  error TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  worker_id TEXT,
  attempt INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 1,
  out_md TEXT,
  out_json TEXT,
  work_dir TEXT,
  label TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status_prio
  ON eval_jobs(status, priority DESC, created_at ASC);
"""

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class JobStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def enqueue(
        self,
        *,
        model: str,
        packs: list[str] | None = None,
        k: int = 3,
        concurrency: int = 1,
        rpm: float | None = None,
        scaffold: str = "raw",
        priority: int = 0,
        max_attempts: int = 1,
        label: str | None = None,
        out_md: str | None = None,
        out_json: str | None = None,
        work_dir: str | None = None,
    ) -> str:
        jid = str(uuid.uuid4())
        self._conn.execute(
            """INSERT INTO eval_jobs
            (id, model, packs_json, k, concurrency, rpm, scaffold, priority,
             status, created_at, max_attempts, label, out_md, out_json, work_dir, attempt)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
            (
                jid, model,
                json.dumps(packs) if packs is not None else None,
                k, concurrency, rpm, scaffold, priority,
                JobStatus.QUEUED.value, _now(), max_attempts, label,
                out_md, out_json, work_dir,
            ),
        )
        self._conn.commit()
        return jid

    def claim_next(self, worker_id: str) -> EvalJob | None:
        cur = self._conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        row = cur.execute(
            """SELECT id FROM eval_jobs
               WHERE status=? ORDER BY priority DESC, created_at ASC LIMIT 1""",
            (JobStatus.QUEUED.value,),
        ).fetchone()
        if not row:
            self._conn.commit()
            return None
        jid = row["id"]
        cur.execute(
            """UPDATE eval_jobs SET status=?, worker_id=?, started_at=?, attempt=attempt+1
               WHERE id=? AND status=?""",
            (JobStatus.RUNNING.value, worker_id, _now(), jid, JobStatus.QUEUED.value),
        )
        self._conn.commit()
        return self.get(jid)

    def get(self, job_id: str) -> EvalJob | None:
        row = self._conn.execute(
            "SELECT * FROM eval_jobs WHERE id=?", (job_id,)
        ).fetchone()
        return _row_to_job(row) if row else None

    def list_jobs(self, limit: int = 100) -> list[EvalJob]:
        rows = self._conn.execute(
            "SELECT * FROM eval_jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_job(r) for r in rows]

    def cancel(self, job_id: str) -> bool:
        cur = self._conn.execute(
            "UPDATE eval_jobs SET status=?, finished_at=? WHERE id=? AND status=?",
            (JobStatus.CANCELLED.value, _now(), job_id, JobStatus.QUEUED.value),
        )
        self._conn.commit()
        return cur.rowcount == 1

    def mark_succeeded(self, job_id: str, *, out_md: str, out_json: str) -> None:
        self._conn.execute(
            """UPDATE eval_jobs SET status=?, finished_at=?, out_md=?, out_json=?, error=NULL
               WHERE id=?""",
            (JobStatus.SUCCEEDED.value, _now(), out_md, out_json, job_id),
        )
        self._conn.commit()

    def mark_failed(self, job_id: str, error: str) -> None:
        self._conn.execute(
            """UPDATE eval_jobs SET status=?, finished_at=?, error=? WHERE id=?""",
            (JobStatus.FAILED.value, _now(), error[:4000], job_id),
        )
        self._conn.commit()

    def requeue_stale(self, stale_seconds: float = 3600) -> int:
        """Mark long-running jobs failed so they can be retried manually."""
        # Implementation: compare started_at to now; set failed with reason stale
        ...
```

Implement `_row_to_job` parsing `packs_json`. Implement `requeue_stale` fully (no `...`).

- [ ] **Step 4: Extend tests** — cancel only when queued; mark_succeeded; list order

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_queue_store.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/dsm_ae/queue tests/test_queue_store.py
git commit -m "feat(queue): SQLite job store for eval queue"
```

---

### Task 2: CLI `queue` commands

**Files:**
- Modify: `src/dsm_ae/cli.py`
- Test: `tests/test_queue_cli.py` (optional typer CliRunner)

**Interfaces:**
- Consumes: `JobStore`
- Produces: `dsm-ae queue enqueue|enqueue-batch|list|status|cancel|retry`

- [ ] **Step 1: Add nested Typer app**

```python
# in cli.py
queue_app = typer.Typer(help="Evaluation job queue")
app.add_typer(queue_app, name="queue")

@queue_app.command("enqueue")
def queue_enqueue(
    model: str = typer.Option(..., "--model", "-m"),
    packs: Optional[str] = typer.Option(None, "--packs", "-p"),
    k: int = typer.Option(3, "--k"),
    concurrency: int = typer.Option(1, "--concurrency", "-j"),
    rpm: Optional[float] = typer.Option(None, "--rpm"),
    full_suite: bool = typer.Option(False, "--full-suite"),
    priority: int = typer.Option(0, "--priority"),
    label: Optional[str] = typer.Option(None, "--label"),
    db: Path = typer.Option(Path("data/queue.db"), "--db"),
) -> None:
    from dsm_ae.queue.store import JobStore
    from dsm_ae.packs.registry import list_packs
    pack_list = list_packs() if full_suite else (
        [x.strip() for x in packs.split(",")] if packs else None
    )
    store = JobStore(db)
    jid = store.enqueue(
        model=model, packs=pack_list, k=k, concurrency=concurrency,
        rpm=rpm, priority=priority, label=label,
    )
    console.print(f"enqueued [bold]{jid}[/bold] model={model}")
```

Also implement `enqueue-batch` (comma-separated models), `list`, `status`, `cancel`, `retry` (re-insert or set status queued if failed).

- [ ] **Step 2: Manual smoke**

```bash
pip install -e .
dsm-ae queue enqueue -m mock/well_attuned -p hello_metacog --k 1
dsm-ae queue list
```

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(queue): CLI enqueue/list/cancel"
```

---

### Task 3: Worker runs diagnose + rebuilds matrix

**Files:**
- Create: `src/dsm_ae/queue/worker.py`
- Modify: `src/dsm_ae/cli.py` (`worker` command)
- Test: `tests/test_queue_worker.py`

**Interfaces:**
- Consumes: `JobStore.claim_next`, `diagnose`, html report builder
- Produces: report files under `reports/queue/`, updated matrix HTML

- [ ] **Step 1: Failing e2e test**

```python
# tests/test_queue_worker.py
from pathlib import Path
from dsm_ae.queue.store import JobStore
from dsm_ae.queue.worker import run_one

def test_run_one_mock(tmp_path: Path):
    db = tmp_path / "q.db"
    reports = tmp_path / "reports"
    store = JobStore(db)
    jid = store.enqueue(model="mock/well_attuned", packs=["hello_metacog"], k=2)
    ok = run_one(store, worker_id="t", reports_dir=reports, models_yaml=None)
    assert ok is True
    job = store.get(jid)
    assert job.status.value == "succeeded"
    assert Path(job.out_json).is_file()
```

- [ ] **Step 2: Implement `run_one` + `run_loop`**

```python
# src/dsm_ae/queue/worker.py
from __future__ import annotations
import traceback
from pathlib import Path
from dsm_ae.diagnose import diagnose
from dsm_ae.queue.paths import job_report_paths
from dsm_ae.queue.store import JobStore
from dsm_ae.report import render_markdown
import json

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
    except Exception as e:
        store.mark_failed(job.id, traceback.format_exc())
        return False

def run_loop(..., once: bool = False, poll_s: float = 2.0):
    while True:
        result = run_one(...)
        if once and result is None:
            return
        if result is None:
            time.sleep(poll_s)

def _rebuild_matrix(reports_dir: Path, matrix_out: Path | None):
    # Call scripts/json_to_html_report.main or subprocess
    ...
```

Wire CLI:

```bash
dsm-ae worker --db data/queue.db --models-yaml models.yaml --reports-dir reports --once
```

- [ ] **Step 3: pytest**

```bash
pytest tests/test_queue_worker.py tests/test_queue_store.py -v
```

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(queue): worker runs diagnose and rebuilds HTML matrix"
```

---

### Task 4: Migrate batch scripts + README

**Files:**
- Modify: `scripts/run_full_suite_pangu.sh` (pattern for others)
- Modify: `README.md`
- Modify: `src/dsm_ae/cli.py` — make `diagnose-batch` enqueue+worker optional or document deprecation

- [ ] **Step 1: Pattern for suite scripts**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PACKS=$(PYTHONPATH=src python3 -c "from dsm_ae.packs.registry import list_packs; print(','.join(list_packs()))")
for M in Beta_pangu_92b Beta_pangu_505b; do
  dsm-ae queue enqueue -m "$M" -p "$PACKS" --k 3 -j 2 --rpm 10 --label "${M}-full"
done
dsm-ae worker --models-yaml models.yaml --reports-dir reports --once
```

Prefer **not** rewriting all scripts mid-run of production suite; add `scripts/run_full_suite_via_queue.sh` as the new path and leave old scripts until next maintenance window.

- [ ] **Step 2: README section “Queued evaluation”**

Document enqueue → worker → matrix flow; clarify models.yaml is credentials-only.

- [ ] **Step 3: Commit**

```bash
git commit -am "docs: queued evaluation workflow and suite helper script"
```

---

### Task 5 (optional): Thin HTTP status UI

**Files:**
- Create: `src/dsm_ae/queue/web.py`
- Modify: `pyproject.toml` optional dep `web = ["fastapi", "uvicorn"]`
- Modify: `cli.py` → `dsm-ae serve-queue --port 8765`

- [ ] Serve static `reports/` + `GET/POST /api/jobs`
- [ ] Form at `/queue` for model/packs/k
- [ ] Bind 127.0.0.1 by default; funnel only static matrix if public

Skip if time-boxed; CLI+worker already meet the core goal.

---

## Self-review

| Spec requirement | Task |
|------------------|------|
| SQLite jobs | Task 1 |
| CLI enqueue/list/cancel | Task 2 |
| Worker + diagnose | Task 3 |
| HTML progressive update | Task 3 `_rebuild_matrix` |
| models.yaml credentials only | Tasks 2–3 (no keys in store) |
| Mock offline CI | Task 3 test |
| Script migration | Task 4 |
| Thin UI | Task 5 optional |

No TBD placeholders in task code blocks; `requeue_stale` must be completed in Task 1 (not left as `...` in real implementation).

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-10-eval-queue.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
