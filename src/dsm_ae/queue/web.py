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

from dsm_ae.litellm_client import make_client
from dsm_ae.packs.registry import list_packs
from dsm_ae.queue.models import EvalJob
from dsm_ae.queue.progress import (
    progress_path_for,
    read_progress,
    secrets_path_for,
    write_progress,
    write_secret,
)
from dsm_ae.queue.store import JobStore
from dsm_ae.queue.worker import default_worker_id, run_loop
from dsm_ae.queue.web_html import render_queue_page


class EnqueueBody(BaseModel):
    model: str = Field(..., min_length=1, description="Model id (LiteLLM model name)")
    packs: list[str] | None = None
    packs_csv: str | None = None
    k: int = 3
    concurrency: int = 1
    rpm: float | None = None
    full_suite: bool = False
    priority: int = 0
    label: str | None = None
    # LiteLLM-style connection (optional; falls back to models.yaml / mock)
    api_base: str | None = None
    api_key: str | None = Field(
        default=None, description="Stored in a secrets file, never returned by API"
    )
    timeout: float | None = None
    num_retries: int | None = None


class ConnectionTestBody(BaseModel):
    model: str = Field(..., min_length=1)
    api_base: str | None = None
    api_key: str | None = None
    timeout: float | None = 30.0
    num_retries: int | None = 0


def _job_dict(job: EvalJob) -> dict[str, Any]:
    d = asdict(job)
    d["status"] = job.status.value
    # Never expose secret file path or raw key material to clients.
    d.pop("secret_path", None)
    d["has_api_key"] = bool(job.secret_path)
    d["progress"] = read_progress(job.progress_path)
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
    secrets_dir = db_path.parent / "job_secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)

    app.state.store = store
    app.state.reports_dir = reports_dir
    app.state.models_yaml = yaml_path
    app.state.public_base = base
    app.state.token = resolved_token
    app.state.worker_thread = None
    app.state.secrets_dir = secrets_dir

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
        return _job_dict(job)

    def _extra_from_body(timeout: float | None, num_retries: int | None) -> dict[str, Any] | None:
        extra: dict[str, Any] = {}
        if timeout is not None:
            extra["timeout"] = float(timeout)
        if num_retries is not None:
            extra["num_retries"] = int(num_retries)
        return extra or None

    def _enqueue_from_fields(
        *,
        model: str,
        packs: list[str] | None,
        k: int,
        concurrency: int,
        rpm: float | None,
        priority: int,
        label: str | None,
        api_base: str | None,
        api_key: str | None,
        timeout: float | None,
        num_retries: int | None,
    ) -> EvalJob:
        model = model.strip()
        api_base = (api_base or "").strip() or None
        extra = _extra_from_body(timeout, num_retries)
        jid = store.enqueue(
            model=model,
            packs=packs,
            k=k,
            concurrency=concurrency,
            rpm=rpm,
            priority=priority,
            label=label,
            api_base=api_base,
            extra=extra,
        )
        prog = progress_path_for(reports_dir, jid)
        store.update_paths(jid, progress_path=str(prog))
        write_progress(
            prog,
            {
                "job_id": jid,
                "model": model,
                "phase": "queued",
                "status": "queued",
                "done": 0,
                "total": 0,
                "message": "Queued — waiting for worker",
            },
        )
        if api_key and api_key.strip():
            sp = secrets_path_for(secrets_dir, jid)
            write_secret(sp, api_key=api_key.strip())
            store.update_paths(jid, secret_path=str(sp))
        job = store.get(jid)
        assert job is not None
        return job

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

    @app.get("/api/jobs/{job_id}/progress")
    def api_job_progress(job_id: str) -> dict[str, Any]:
        job = _resolve(store, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        prog = read_progress(job.progress_path) or {
            "job_id": job.id,
            "status": job.status.value,
            "message": job.status.value,
        }
        return prog

    @app.post("/api/test-connection")
    def api_test_connection(
        body: ConnectionTestBody,
        _: None = Depends(require_token),
    ) -> dict[str, Any]:
        model = body.model.strip()
        if model.startswith("mock/"):
            return {
                "ok": True,
                "message": f"Offline mock persona '{model.split('/', 1)[-1]}' — no network call",
            }
        extra: dict[str, Any] = {}
        if body.timeout is not None:
            extra["timeout"] = float(body.timeout)
        if body.num_retries is not None:
            extra["num_retries"] = int(body.num_retries)
        try:
            client = make_client(
                model,
                models_yaml=yaml_path,
                api_base=(body.api_base or "").strip() or None,
                api_key=(body.api_key or "").strip() or None,
                extra=extra or None,
            )
            result = client.complete(
                [{"role": "user", "content": "Reply with the single word: pong"}],
                max_tokens=16,
                temperature=0.0,
            )
            text = (result.content or "").strip()
            return {
                "ok": True,
                "message": f"Endpoint OK — model replied: {text[:200]!r}",
                "preview": text[:200],
            }
        except Exception as e:
            return {"ok": False, "message": f"{type(e).__name__}: {e}"}

    @app.post("/api/jobs")
    def api_enqueue(
        body: EnqueueBody,
        _: None = Depends(require_token),
    ) -> dict[str, Any]:
        pack_list = _parse_packs_list(body.packs, body.packs_csv, body.full_suite)
        job = _enqueue_from_fields(
            model=body.model,
            packs=pack_list,
            k=body.k,
            concurrency=body.concurrency,
            rpm=body.rpm,
            priority=body.priority,
            label=body.label,
            api_base=body.api_base,
            api_key=body.api_key,
            timeout=body.timeout,
            num_retries=body.num_retries,
        )
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
        return HTMLResponse(render_queue_page(store, href, app.state.token is not None, title="DSM-AE"))

    @app.get("/queue", response_class=HTMLResponse)
    def queue_page() -> HTMLResponse:
        return HTMLResponse(
            render_queue_page(store, href, app.state.token is not None, title="Queue")
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
        api_base: str = Form(""),
        api_key: str = Form(""),
        timeout: Optional[float] = Form(None),
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
        _enqueue_from_fields(
            model=model,
            packs=pack_list,
            k=k,
            concurrency=concurrency,
            rpm=None,
            priority=priority,
            label=label.strip() or None,
            api_base=api_base or None,
            api_key=api_key or None,
            timeout=timeout,
            num_retries=2,
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
