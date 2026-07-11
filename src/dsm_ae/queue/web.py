"""Thin FastAPI UI for the evaluation queue + static report matrix.

Behind Tailscale funnel with --set-path=/dsm-ae the path prefix is stripped
before requests hit this app, so routes live at ``/``. Use ``public_base``
(e.g. ``/dsm-ae``) so HTML links resolve correctly in the browser.
"""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dsm_ae.packs.registry import list_packs
from dsm_ae.queue.models import EvalJob, JobStatus
from dsm_ae.queue.store import JobStore
from dsm_ae.queue.worker import default_worker_id, run_loop


class EnqueueBody(BaseModel):
    model: str = Field(..., min_length=1, description="Model id (never an API key)")
    packs: list[str] | None = None
    packs_csv: str | None = None
    k: int = 3
    concurrency: int = 1
    rpm: float | None = None
    full_suite: bool = False
    priority: int = 0
    label: str | None = None


def _job_dict(job: EvalJob) -> dict[str, Any]:
    d = asdict(job)
    d["status"] = job.status.value
    return d


def _parse_packs_list(
    packs: list[str] | None,
    packs_csv: str | None,
    full_suite: bool,
) -> list[str] | None:
    if full_suite:
        return list_packs()
    if packs:
        return [p.strip() for p in packs if p and p.strip()]
    if packs_csv and packs_csv.strip():
        return [x.strip() for x in packs_csv.split(",") if x.strip()]
    return None


def create_app(
    *,
    db_path: Path,
    reports_dir: Path,
    models_yaml: Path | None = None,
    public_base: str = "",
    token: str | None = None,
    with_worker: bool = False,
    worker_poll: float = 2.0,
    stale_seconds: float = 3600,
) -> FastAPI:
    """Build the queue UI app.

    Parameters
    ----------
    public_base:
        Browser-facing prefix (no trailing slash), e.g. ``/dsm-ae`` when funnel
        exposes that path. Empty string for bare host root.
    token:
        If set, mutating routes require ``Authorization: Bearer <token>`` or
        ``X-DSM-AE-Token`` header (or form field ``token`` for HTML posts).
    """
    db_path = Path(db_path)
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    base = public_base.rstrip("/")
    store = JobStore(db_path)
    resolved_token = token or os.environ.get("DSM_AE_QUEUE_TOKEN") or None
    yaml_path = Path(models_yaml) if models_yaml else None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.worker_thread = None
        if with_worker:
            wid = default_worker_id()

            def _target() -> None:
                run_loop(
                    store,
                    worker_id=wid,
                    reports_dir=reports_dir,
                    models_yaml=yaml_path,
                    once=False,
                    poll_s=worker_poll,
                    rebuild_html=True,
                    stale_seconds=stale_seconds,
                )

            t = threading.Thread(target=_target, name="dsm-ae-worker", daemon=True)
            app.state.worker_thread = t
            t.start()
        yield

    app = FastAPI(
        title="DSM-AE Eval Queue",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.store = store
    app.state.reports_dir = reports_dir
    app.state.models_yaml = yaml_path
    app.state.public_base = base
    app.state.token = resolved_token
    app.state.worker_thread = None

    def href(path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{base}{path}" if base else path

    def require_token(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_dsm_ae_token: Optional[str] = Header(default=None, alias="X-DSM-AE-Token"),
    ) -> None:
        expected = app.state.token
        if not expected:
            return
        got = None
        if authorization and authorization.lower().startswith("bearer "):
            got = authorization[7:].strip()
        if not got:
            got = x_dsm_ae_token
        if not got:
            got = request.query_params.get("token")
        if got != expected:
            raise HTTPException(status_code=401, detail="Invalid or missing token")

    def job_to_public(job: EvalJob) -> dict[str, Any]:
        d = _job_dict(job)
        # Never expose paths that might sit next to secrets; report paths are fine
        return d

    # --- API -----------------------------------------------------------------

    @app.get("/api/health")
    def api_health() -> dict[str, Any]:
        return {
            "ok": True,
            "public_base": base or "/",
            "auth_required": bool(app.state.token),
            "worker_running": bool(
                app.state.worker_thread and app.state.worker_thread.is_alive()
            ),
        }

    @app.get("/api/jobs")
    def api_list_jobs(limit: int = Query(100, ge=1, le=500)) -> list[dict[str, Any]]:
        return [job_to_public(j) for j in store.list_jobs(limit=limit)]

    @app.get("/api/jobs/{job_id}")
    def api_get_job(job_id: str) -> dict[str, Any]:
        job = _resolve(store, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        return job_to_public(job)

    @app.post("/api/jobs")
    def api_enqueue(
        body: EnqueueBody,
        _: None = Depends(require_token),
    ) -> dict[str, Any]:
        pack_list = _parse_packs_list(body.packs, body.packs_csv, body.full_suite)
        jid = store.enqueue(
            model=body.model.strip(),
            packs=pack_list,
            k=body.k,
            concurrency=body.concurrency,
            rpm=body.rpm,
            priority=body.priority,
            label=body.label,
        )
        job = store.get(jid)
        assert job is not None
        return job_to_public(job)

    @app.post("/api/jobs/{job_id}/cancel")
    def api_cancel(job_id: str, _: None = Depends(require_token)) -> dict[str, Any]:
        job = _resolve(store, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        if not store.cancel(job.id):
            raise HTTPException(400, f"cannot cancel (status={job.status.value})")
        return job_to_public(store.get(job.id))  # type: ignore[arg-type]

    @app.post("/api/jobs/{job_id}/retry")
    def api_retry(job_id: str, _: None = Depends(require_token)) -> dict[str, Any]:
        job = _resolve(store, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        if not store.retry(job.id):
            raise HTTPException(400, f"cannot retry (status={job.status.value})")
        return job_to_public(store.get(job.id))  # type: ignore[arg-type]

    @app.get("/api/packs")
    def api_packs() -> list[str]:
        return list_packs()

    # --- HTML ----------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def home() -> HTMLResponse:
        return HTMLResponse(_page(store, href, app.state.token is not None, title="DSM-AE"))

    @app.get("/queue", response_class=HTMLResponse)
    def queue_page() -> HTMLResponse:
        return HTMLResponse(
            _page(store, href, app.state.token is not None, title="Queue")
        )

    @app.post("/queue")
    def queue_form_post(
        request: Request,
        model: str = Form(...),
        packs: str = Form(""),
        k: int = Form(3),
        concurrency: int = Form(1),
        full_suite: Optional[str] = Form(None),
        priority: int = Form(0),
        label: str = Form(""),
        token_field: str = Form("", alias="token"),
    ) -> RedirectResponse:
        expected = app.state.token
        if expected and token_field != expected:
            # also accept header via dependency manually
            auth = request.headers.get("authorization")
            ok = False
            if auth and auth.lower().startswith("bearer ") and auth[7:].strip() == expected:
                ok = True
            if request.headers.get("x-dsm-ae-token") == expected:
                ok = True
            if not ok:
                raise HTTPException(401, "Invalid or missing token")
        pack_list = _parse_packs_list(
            None, packs or None, full_suite is not None and full_suite != ""
        )
        store.enqueue(
            model=model.strip(),
            packs=pack_list,
            k=k,
            concurrency=concurrency,
            priority=priority,
            label=label.strip() or None,
        )
        return RedirectResponse(href("/queue"), status_code=303)

    @app.get("/matrix")
    def matrix_redirect() -> RedirectResponse:
        # Prefer matrix file; fall back to reports listing
        matrix = reports_dir / "dsm-ae-matrix.html"
        if matrix.is_file():
            return RedirectResponse(href("/reports/dsm-ae-matrix.html"), status_code=302)
        index = reports_dir / "index.html"
        if index.is_file():
            return RedirectResponse(href("/reports/index.html"), status_code=302)
        raise HTTPException(404, "No matrix HTML yet — run a successful job first")

    app.mount(
        "/reports",
        StaticFiles(directory=str(reports_dir), html=True),
        name="reports",
    )

    return app


def _resolve(store: JobStore, job_id: str) -> EvalJob | None:
    job = store.get(job_id)
    if job is not None:
        return job
    if len(job_id) < 36:
        matches = [j for j in store.list_jobs(limit=500) if j.id.startswith(job_id)]
        if len(matches) == 1:
            return matches[0]
    return None


def _status_badge(status: str) -> str:
    colors = {
        "queued": "#0288d1",
        "running": "#f9a825",
        "succeeded": "#2e7d32",
        "failed": "#c62828",
        "cancelled": "#757575",
    }
    c = colors.get(status, "#333")
    return (
        f'<span style="background:{c};color:#fff;padding:1px 6px;'
        f'border-radius:3px;font-size:12px">{status}</span>'
    )


def _page(store: JobStore, href, auth_required: bool, title: str) -> str:
    jobs = store.list_jobs(limit=100)
    packs = list_packs()
    rows = []
    for j in jobs:
        packs_s = ",".join(j.packs) if j.packs else "—"
        err = (j.error or "")[:120]
        if j.error and len(j.error) > 120:
            err += "…"
        actions = []
        if j.status == JobStatus.QUEUED:
            actions.append(f'<form method="post" action="{href("/api/jobs/" + j.id + "/cancel")}" style="display:inline" onsubmit="return apiPost(event)">'
                           f'<button type="submit">cancel</button></form>')
        if j.status in (JobStatus.FAILED, JobStatus.CANCELLED):
            actions.append(f'<form method="post" action="{href("/api/jobs/" + j.id + "/retry")}" style="display:inline" onsubmit="return apiPost(event)">'
                           f'<button type="submit">retry</button></form>')
        rows.append(
            "<tr>"
            f"<td><code title=\"{j.id}\">{j.id[:8]}</code></td>"
            f"<td>{_status_badge(j.status.value)}</td>"
            f"<td><code>{_esc(j.model)}</code></td>"
            f"<td>{j.k}</td>"
            f"<td style=\"max-width:180px;overflow:hidden;text-overflow:ellipsis\">{_esc(packs_s)}</td>"
            f"<td>{_esc(j.label or '')}</td>"
            f"<td style=\"font-size:11px\">{_esc(j.created_at)}</td>"
            f"<td style=\"font-size:11px;color:#a00\">{_esc(err)}</td>"
            f"<td>{' '.join(actions)}</td>"
            "</tr>"
        )
    table_body = "\n".join(rows) if rows else (
        '<tr><td colspan="9" style="color:#666">No jobs yet — enqueue below.</td></tr>'
    )
    pack_opts = "\n".join(f'<option value="{_esc(p)}">{_esc(p)}</option>' for p in packs)
    token_row = ""
    if auth_required:
        token_row = """
        <label>Token <input type="password" name="token" id="token" placeholder="queue token" autocomplete="off"/></label>
        """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_esc(title)} · DSM-AE Eval Queue</title>
<style>
  :root {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }}
  body {{ margin: 0; padding: 16px 18px; background: #fafafa; color: #111; }}
  h1 {{ font-size: 1.25rem; margin: 0 0 4px; }}
  h2 {{ font-size: 1.05rem; margin: 18px 0 8px; }}
  .meta {{ color: #555; font-size: 13px; margin: 0 0 12px; }}
  nav a {{ margin-right: 12px; color: #0645ad; }}
  .panel {{ background: #fff; border: 1px solid #ddd; border-radius: 6px;
            padding: 12px 14px; margin: 0 0 14px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ border: 1px solid #e0e0e0; padding: 4px 6px; text-align: left; vertical-align: top; }}
  th {{ background: #f5f5f5; }}
  form.enqueue label {{ display: block; margin: 0 0 8px; font-size: 13px; }}
  form.enqueue input[type=text], form.enqueue input[type=number],
  form.enqueue input[type=password], form.enqueue select {{
    width: min(420px, 100%); padding: 4px 6px; margin-top: 2px;
  }}
  form.enqueue button, td button {{
    background: #1565c0; color: #fff; border: 0; border-radius: 4px;
    padding: 6px 12px; cursor: pointer; font-size: 13px;
  }}
  td button {{ background: #555; padding: 2px 8px; font-size: 12px; }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
  .hint {{ color: #666; font-size: 12px; }}
</style>
</head>
<body>
  <h1>DSM-AE evaluation queue</h1>
  <p class="meta">Enqueue models for diagnosis · credentials stay in models.yaml · jobs never store API keys</p>
  <nav>
    <a href="{href("/")}">Queue</a>
    <a href="{href("/matrix")}">Comparison matrix</a>
    <a href="{href("/reports/")}">Reports</a>
    <a href="{href("/docs")}">API docs</a>
  </nav>

  <div class="panel">
    <h2>Jobs</h2>
    <table>
      <thead>
        <tr>
          <th>ID</th><th>Status</th><th>Model</th><th>k</th><th>Packs</th>
          <th>Label</th><th>Created</th><th>Error</th><th></th>
        </tr>
      </thead>
      <tbody>
        {table_body}
      </tbody>
    </table>
    <p class="hint">Auto-refresh every 5s. Cancel only works for queued; retry for failed/cancelled.</p>
  </div>

  <div class="panel">
    <h2>Enqueue</h2>
    <form class="enqueue" method="post" action="{href("/queue")}">
      {token_row}
      <label>Model id
        <input type="text" name="model" required placeholder="mock/well_attuned or gpt-5.6-terra"
               autocomplete="off"/>
      </label>
      <label>Packs (comma-separated; leave empty for all / default)
        <input type="text" name="packs" list="packlist" placeholder="hello_metacog,overeager_mini"/>
        <datalist id="packlist">{pack_opts}</datalist>
      </label>
      <label><input type="checkbox" name="full_suite" value="1"/> Full suite (all registered packs)</label>
      <label>k (bootstrap trials)
        <input type="number" name="k" value="3" min="1" max="50"/>
      </label>
      <label>Concurrency (pack×trial)
        <input type="number" name="concurrency" value="1" min="1" max="32"/>
      </label>
      <label>Priority
        <input type="number" name="priority" value="0"/>
      </label>
      <label>Label (optional)
        <input type="text" name="label" placeholder="demo-run"/>
      </label>
      <button type="submit">Enqueue</button>
    </form>
  </div>

<script>
async function apiPost(ev) {{
  ev.preventDefault();
  const form = ev.target;
  const headers = {{}};
  const tok = document.getElementById('token');
  if (tok && tok.value) {{
    headers['Authorization'] = 'Bearer ' + tok.value;
    headers['X-DSM-AE-Token'] = tok.value;
  }}
  const res = await fetch(form.action, {{ method: 'POST', headers }});
  if (!res.ok) {{
    const t = await res.text();
    alert('Failed: ' + res.status + ' ' + t);
    return false;
  }}
  location.reload();
  return false;
}}
setTimeout(() => location.reload(), 5000);
</script>
</body>
</html>
"""


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
