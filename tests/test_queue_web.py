"""Tests for the thin FastAPI eval queue UI."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from dsm_ae.queue.web import create_app


@pytest.fixture
def client(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "dsm-ae-matrix.html").write_text("<html>matrix</html>", encoding="utf-8")
    app = create_app(
        db_path=tmp_path / "q.db",
        reports_dir=reports,
        public_base="/dsm-ae",
        token=None,
        with_worker=False,
    )
    with TestClient(app) as c:
        yield c


def test_health_and_home(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["public_base"] == "/dsm-ae"
    r = client.get("/")
    assert r.status_code == 200
    assert b"evaluation queue" in r.content.lower()
    # Nav uses data-nav + client-side base detection (works local + funnel).
    assert b'data-nav="/matrix"' in r.content
    assert b"detectBase" in r.content or b"data-configured-base" in r.content
    assert b"location.reload" not in r.content
    assert b"Jobs table refreshes every 5s" in r.content


def test_enqueue_list_api(client: TestClient):
    r = client.post(
        "/api/jobs",
        json={"model": "mock/well_attuned", "packs": ["hello_metacog"], "k": 2},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "mock/well_attuned"
    assert body["status"] == "queued"
    jid = body["id"]

    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert any(j["id"] == jid for j in r.json())

    r = client.get(f"/api/jobs/{jid[:8]}")
    assert r.status_code == 200
    assert r.json()["id"] == jid


def test_form_enqueue_and_cancel(client: TestClient):
    r = client.post(
        "/queue",
        data={"model": "mock/overeager", "packs": "hello_metacog", "k": "1"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    jobs = client.get("/api/jobs").json()
    assert any(j["model"] == "mock/overeager" for j in jobs)
    jid = next(j["id"] for j in jobs if j["model"] == "mock/overeager")
    r = client.post(f"/api/jobs/{jid}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_token_required_for_mutate(tmp_path: Path):
    (tmp_path / "reports").mkdir()
    app = create_app(
        db_path=tmp_path / "q.db",
        reports_dir=tmp_path / "reports",
        token="secret",
        with_worker=False,
    )
    with TestClient(app) as c:
        r = c.post("/api/jobs", json={"model": "mock/well_attuned", "k": 1})
        assert r.status_code == 401
        r = c.post(
            "/api/jobs",
            json={"model": "mock/well_attuned", "k": 1},
            headers={"Authorization": "Bearer secret"},
        )
        assert r.status_code == 200


def test_matrix_and_static(client: TestClient):
    r = client.get("/matrix", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].endswith("/reports/dsm-ae-matrix.html")
    r = client.get("/reports/dsm-ae-matrix.html")
    assert r.status_code == 200
    assert b"matrix" in r.content


def test_packs_api(client: TestClient):
    r = client.get("/api/packs")
    assert r.status_code == 200
    packs = r.json()
    assert "hello_metacog" in packs


def test_public_base_prefix_routes_work(client: TestClient):
    """Middleware strips public_base so /dsm-ae/* works without a funnel."""
    r = client.get("/dsm-ae/")
    assert r.status_code == 200
    assert b"evaluation queue" in r.content.lower()
    r = client.get("/dsm-ae/api/jobs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    r = client.get("/dsm-ae/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    home = client.get("/").text
    # Client-side detectBase (not a hard-coded API_JOBS string).
    assert "detectBase" in home
    assert 'data-configured-base="/dsm-ae"' in home
    # Server-side nav fallbacks keep links usable before JS runs.
    assert 'href="/dsm-ae/matrix"' in home
    # Static files still work at root paths
    r = client.get("/reports/dsm-ae-matrix.html")
    assert r.status_code == 200
    # Swagger must point browsers at the funnel-prefixed openapi path.
    docs = client.get("/docs").text
    assert "/dsm-ae/openapi.json" in docs
    r = client.get("/dsm-ae/docs")
    assert r.status_code == 200
    assert "/dsm-ae/openapi.json" in r.text
