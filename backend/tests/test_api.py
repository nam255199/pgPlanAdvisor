import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import create_app

    return TestClient(create_app())


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_analyze_happy_path(client, fixture):
    r = client.post("/api/v1/analyze", json={"plan": fixture("seq_scan_heavy.json"), "query": "select 1"})
    assert r.status_code == 200
    body = r.json()
    assert body["top_findings"]
    assert body["query"] == "select 1"
    assert "x-request-id" in {k.lower() for k in r.headers}


def test_analyze_rejects_garbage_plan(client):
    r = client.post("/api/v1/analyze", json={"plan": "not a plan, just prose about databases"})
    assert r.status_code == 400
    assert "detail" in r.json()


def test_analyze_export_returns_markdown(client, fixture):
    r = client.post("/api/v1/analyze/export", json={"plan": fixture("seq_scan_heavy.json")})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert r.text.startswith("# pgPlanAdvisor report")


def test_history_disabled_by_default(client):
    r = client.get("/api/v1/history")
    assert r.status_code == 404


def test_save_without_history_enabled_is_rejected(client, fixture):
    r = client.post("/api/v1/analyze", json={"plan": fixture("seq_scan_heavy.json"), "save": True})
    assert r.status_code == 400


def test_request_id_is_echoed_back(client):
    r = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["x-request-id"] == "abc123"
