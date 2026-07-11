"""Thin FastAPI UI for the evaluation queue + static report matrix.

Behind Tailscale funnel with --set-path=/dsm-ae the path prefix is stripped
before requests hit this app, so routes live at ``/``. Use ``public_base``
(e.g. ``/dsm-ae``) so HTML links resolve correctly in the browser.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Query, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dsm_ae.packs.registry import list_packs
from dsm_ae.queue.models import EvalJob
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
        # Custom /docs below so openapi_url includes public_base (funnel-safe).
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.store = store
    app.state.reports_dir = reports_dir
    app.state.models_yaml = yaml_path
    app.state.public_base = base
    app.state.token = resolved_token
    app.state.worker_thread = None

    # Optional dual-access: accept /dsm-ae/... when the prefix was NOT already
    # stripped (e.g. local curl http://127.0.0.1:8765/dsm-ae/api/jobs).
    # Do not rewrite root_path on every request — that breaks StaticFiles.
    if base:

        @app.middleware("http")
        async def _strip_public_base(request: Request, call_next):  # type: ignore[no-untyped-def]
            path = request.scope.get("path", "") or ""
            if path == base or path.startswith(base + "/"):
                request.scope["path"] = path[len(base) :] or "/"
            return await call_next(request)

    def href(path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{base}{path}" if base else path

    @app.get("/docs", include_in_schema=False)
    def swagger_ui() -> HTMLResponse:
        # Browser must fetch openapi under the funnel prefix; the app itself still
        # serves the schema at /openapi.json (proxy strips public_base).
        return get_swagger_ui_html(
            openapi_url=href("/openapi.json"),
            title=f"{app.title} - Swagger UI",
        )

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


def _page(store: JobStore, href, auth_required: bool, title: str) -> str:
    packs = list_packs()
    pack_opts = "\n".join(f'<option value="{_esc(p)}">{_esc(p)}</option>' for p in packs)
    token_row = ""
    if auth_required:
        token_row = """
        <label>Token
          <input type="password" name="token" id="token" placeholder="queue token"
                 autocomplete="off" data-persist="token"/>
        </label>
        """
    # Derive configured base from href helper (e.g. "/dsm-ae"); JS re-detects live.
    sample = href("/queue")
    configured_base = ""
    if sample.startswith("/") and sample.endswith("/queue"):
        configured_base = sample[: -len("/queue")]
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
  form.enqueue button, button.action {{
    background: #1565c0; color: #fff; border: 0; border-radius: 4px;
    padding: 6px 12px; cursor: pointer; font-size: 13px;
  }}
  button.action {{ background: #555; padding: 2px 8px; font-size: 12px; }}
  button.action:disabled {{ opacity: 0.5; cursor: not-allowed; }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
  .hint {{ color: #666; font-size: 12px; }}
  .hint .ok {{ color: #2e7d32; }}
  .hint .err {{ color: #c62828; }}
  .status {{ color: #fff; padding: 1px 6px; border-radius: 3px; font-size: 12px; }}
  .st-queued {{ background: #0288d1; }}
  .st-running {{ background: #f9a825; color: #111; }}
  .st-succeeded {{ background: #2e7d32; }}
  .st-failed {{ background: #c62828; }}
  .st-cancelled {{ background: #757575; }}
  #flash {{ margin: 0 0 10px; font-size: 13px; min-height: 1.2em; }}
  #flash.ok {{ color: #2e7d32; }}
  #flash.err {{ color: #c62828; }}
</style>
</head>
<body data-configured-base="{_esc(configured_base)}">
  <h1>DSM-AE evaluation queue</h1>
  <p class="meta">Enqueue models for diagnosis · credentials stay in models.yaml · jobs never store API keys</p>
  <nav>
    <a href="{href("/")}" data-nav="/">Queue</a>
    <a href="{href("/matrix")}" data-nav="/matrix" target="_blank" rel="noopener">Comparison matrix</a>
    <a href="{href("/reports/")}" data-nav="/reports/" target="_blank" rel="noopener">Reports</a>
    <a href="{href("/docs")}" data-nav="/docs" target="_blank" rel="noopener">API docs</a>
  </nav>
  <div id="flash" role="status" aria-live="polite"></div>

  <div class="panel">
    <h2>Jobs <span id="jobs-updated" class="hint"></span></h2>
    <table>
      <thead>
        <tr>
          <th>ID</th><th>Status</th><th>Model</th><th>k</th><th>Packs</th>
          <th>Label</th><th>Created</th><th>Error</th><th></th>
        </tr>
      </thead>
      <tbody id="jobs-body">
        <tr><td colspan="9" style="color:#666">Loading…</td></tr>
      </tbody>
    </table>
    <p class="hint">Jobs table refreshes every 5s without reloading the page (form fields stay intact). Cancel: queued only; retry: failed/cancelled.</p>
  </div>

  <div class="panel">
    <h2>Enqueue</h2>
    <form class="enqueue" id="enqueue-form" method="post" action="{href("/queue")}">
      {token_row}
      <label>Model id
        <input type="text" name="model" id="f-model" required
               placeholder="mock/well_attuned or gpt-5.6-terra"
               autocomplete="off" data-persist="model"/>
      </label>
      <label>Packs (comma-separated; leave empty for all / default)
        <input type="text" name="packs" id="f-packs" list="packlist"
               placeholder="hello_metacog,overeager_mini" data-persist="packs"/>
        <datalist id="packlist">{pack_opts}</datalist>
      </label>
      <label><input type="checkbox" name="full_suite" id="f-full" value="1" data-persist="full_suite"/> Full suite (all registered packs)</label>
      <label>k (bootstrap trials)
        <input type="number" name="k" id="f-k" value="3" min="1" max="50" data-persist="k"/>
      </label>
      <label>Concurrency (pack×trial)
        <input type="number" name="concurrency" id="f-concurrency" value="1" min="1" max="32" data-persist="concurrency"/>
      </label>
      <label>Priority
        <input type="number" name="priority" id="f-priority" value="0" data-persist="priority"/>
      </label>
      <label>Label (optional)
        <input type="text" name="label" id="f-label" placeholder="demo-run" data-persist="label"/>
      </label>
      <button type="submit" id="enqueue-btn">Enqueue</button>
    </form>
  </div>

<script>
(function () {{
  const AUTH_REQUIRED = {json.dumps(auth_required)};
  const STORAGE_KEY = "dsm-ae-queue-form-v1";
  const POLL_MS = 5000;

  // Resolve public base so the same server works on :8765 and funnel /dsm-ae.
  function detectBase() {{
    const p = location.pathname || "/";
    if (p === "/dsm-ae" || p.startsWith("/dsm-ae/")) return "/dsm-ae";
    const configured = (document.body.dataset.configuredBase || "").replace(/\\/$/, "");
    if (configured && (p === configured || p.startsWith(configured + "/"))) {{
      return configured;
    }}
    // Local root (or any non-prefixed path): never force funnel prefix.
    return "";
  }}
  const BASE = detectBase();
  function href(path) {{
    if (!path.startsWith("/")) path = "/" + path;
    return BASE + path;
  }}
  const API_JOBS = href("/api/jobs");

  // Wire nav + form action to the live base (avoids hard-coded /dsm-ae on localhost).
  document.querySelectorAll("a[data-nav]").forEach((a) => {{
    a.setAttribute("href", href(a.getAttribute("data-nav") || "/"));
  }});
  const formEl = document.getElementById("enqueue-form");
  if (formEl) formEl.setAttribute("action", href("/queue"));

  function flash(msg, ok) {{
    const el = document.getElementById("flash");
    el.textContent = msg || "";
    el.className = msg ? (ok ? "ok" : "err") : "";
  }}

  function authHeaders() {{
    const headers = {{}};
    const tok = document.getElementById("token");
    if (tok && tok.value) {{
      headers["Authorization"] = "Bearer " + tok.value;
      headers["X-DSM-AE-Token"] = tok.value;
    }}
    return headers;
  }}

  function persistForm() {{
    const data = {{}};
    document.querySelectorAll("[data-persist]").forEach((el) => {{
      const k = el.getAttribute("data-persist");
      if (el.type === "checkbox") data[k] = el.checked;
      else data[k] = el.value;
    }});
    try {{ sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data)); }} catch (e) {{}}
  }}

  function restoreForm() {{
    let data = null;
    try {{ data = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null"); }} catch (e) {{}}
    if (!data) return;
    document.querySelectorAll("[data-persist]").forEach((el) => {{
      const k = el.getAttribute("data-persist");
      if (!(k in data)) return;
      if (el.type === "checkbox") el.checked = !!data[k];
      else if (data[k] !== undefined && data[k] !== null) el.value = data[k];
    }});
  }}

  function esc(s) {{
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }}

  function badge(status) {{
    return '<span class="status st-' + esc(status) + '">' + esc(status) + "</span>";
  }}

  function renderJobs(jobs) {{
    const tbody = document.getElementById("jobs-body");
    if (!jobs || !jobs.length) {{
      tbody.innerHTML = '<tr><td colspan="9" style="color:#666">No jobs yet — enqueue below.</td></tr>';
      return;
    }}
    tbody.innerHTML = jobs.map((j) => {{
      const packs = (j.packs && j.packs.length) ? j.packs.join(",") : "—";
      let err = j.error || "";
      if (err.length > 120) err = err.slice(0, 120) + "…";
      let actions = "";
      if (j.status === "queued") {{
        actions = '<button type="button" class="action" data-act="cancel" data-id="' +
          esc(j.id) + '">cancel</button>';
      }} else if (j.status === "failed" || j.status === "cancelled") {{
        actions = '<button type="button" class="action" data-act="retry" data-id="' +
          esc(j.id) + '">retry</button>';
      }}
      return "<tr>" +
        '<td><code title="' + esc(j.id) + '">' + esc(j.id.slice(0, 8)) + "</code></td>" +
        "<td>" + badge(j.status) + "</td>" +
        "<td><code>" + esc(j.model) + "</code></td>" +
        "<td>" + esc(j.k) + "</td>" +
        '<td style="max-width:180px;overflow:hidden;text-overflow:ellipsis">' + esc(packs) + "</td>" +
        "<td>" + esc(j.label || "") + "</td>" +
        '<td style="font-size:11px">' + esc(j.created_at || "") + "</td>" +
        '<td style="font-size:11px;color:#a00">' + esc(err) + "</td>" +
        "<td>" + actions + "</td></tr>";
    }}).join("");
  }}

  async function refreshJobs() {{
    try {{
      const res = await fetch(API_JOBS + "?limit=100", {{ cache: "no-store" }});
      if (!res.ok) throw new Error("HTTP " + res.status);
      const jobs = await res.json();
      renderJobs(jobs);
      const u = document.getElementById("jobs-updated");
      u.textContent = "· updated " + new Date().toLocaleTimeString();
      u.className = "hint ok";
    }} catch (e) {{
      const u = document.getElementById("jobs-updated");
      u.textContent = "· refresh failed";
      u.className = "hint err";
    }}
  }}

  async function jobAction(act, id, btn) {{
    if (AUTH_REQUIRED) {{
      const tok = document.getElementById("token");
      if (!tok || !tok.value) {{
        flash("Token required for " + act, false);
        return;
      }}
    }}
    if (btn) btn.disabled = true;
    try {{
      const res = await fetch(API_JOBS + "/" + encodeURIComponent(id) + "/" + act, {{
        method: "POST",
        headers: authHeaders(),
      }});
      if (!res.ok) {{
        const t = await res.text();
        flash(act + " failed: " + res.status + " " + t, false);
        // Refresh so buttons match reality (e.g. job already finished).
        await refreshJobs();
        return;
      }}
      flash(act + " ok", true);
      await refreshJobs();
    }} catch (e) {{
      flash(String(e), false);
      await refreshJobs();
    }} finally {{
      if (btn) btn.disabled = false;
    }}
  }}

  document.getElementById("jobs-body").addEventListener("click", (ev) => {{
    const btn = ev.target.closest("button[data-act]");
    if (!btn) return;
    jobAction(btn.getAttribute("data-act"), btn.getAttribute("data-id"), btn);
  }});

  const form = document.getElementById("enqueue-form");
  form.addEventListener("input", persistForm);
  form.addEventListener("change", persistForm);

  form.addEventListener("submit", async (ev) => {{
    ev.preventDefault();
    persistForm();
    if (AUTH_REQUIRED) {{
      const tok = document.getElementById("token");
      if (!tok || !tok.value) {{
        flash("Token required to enqueue", false);
        return;
      }}
    }}
    const btn = document.getElementById("enqueue-btn");
    btn.disabled = true;
    try {{
      const fd = new FormData(form);
      // Prefer JSON API so we can keep the form without a full navigation.
      const packsCsv = (fd.get("packs") || "").toString().trim();
      const body = {{
        model: (fd.get("model") || "").toString().trim(),
        packs_csv: packsCsv || null,
        k: parseInt(fd.get("k") || "3", 10),
        concurrency: parseInt(fd.get("concurrency") || "1", 10),
        priority: parseInt(fd.get("priority") || "0", 10),
        full_suite: fd.get("full_suite") != null,
        label: ((fd.get("label") || "").toString().trim() || null),
      }};
      const res = await fetch(API_JOBS, {{
        method: "POST",
        headers: Object.assign({{ "Content-Type": "application/json" }}, authHeaders()),
        body: JSON.stringify(body),
      }});
      if (!res.ok) {{
        const t = await res.text();
        flash("Enqueue failed: " + res.status + " " + t, false);
        return;
      }}
      const job = await res.json();
      flash("Enqueued " + (job.id || "").slice(0, 8) + " · " + job.model, true);
      // Clear model/label after success so re-submit is intentional; keep token/k/etc.
      const model = document.getElementById("f-model");
      const label = document.getElementById("f-label");
      if (model) model.value = "";
      if (label) label.value = "";
      persistForm();
      await refreshJobs();
    }} catch (e) {{
      flash(String(e), false);
    }} finally {{
      btn.disabled = false;
    }}
  }});

  restoreForm();
  refreshJobs();
  setInterval(refreshJobs, POLL_MS);
}})();
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
