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


def test_compare_endpoint_reports_regression(client, fixture):
    r = client.post(
        "/api/v1/compare",
        json={
            "baseline": {"plan": fixture("healthy_plan.json")},
            "current": {"plan": fixture("seq_scan_heavy.json")},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "regressed"
    assert body["runtime_delta_ms"] > 0
    assert any(f["rule_id"] == "seq_scan_expensive" for f in body["findings_added"])


def test_compare_endpoint_rejects_garbage_plan(client, fixture):
    r = client.post(
        "/api/v1/compare",
        json={
            "baseline": {"plan": fixture("healthy_plan.json")},
            "current": {"plan": "not a plan at all"},
        },
    )
    assert r.status_code == 400


def test_analyze_batch_finds_and_analyzes_entries(client):
    log_text = (
        "2024-01-01 12:00:00 UTC [1]: LOG:  duration: 900.5 ms  plan:\n"
        '        {"Plan": {"Node Type": "Seq Scan", "Relation Name": "orders", '
        '"Plan Rows": 100, "Actual Rows": 50000, "Actual Total Time": 900.5, '
        '"Actual Loops": 1, "Rows Removed by Filter": 100000, "Filter": "(status = \'pending\'::text)"}, '
        '"Execution Time": 900.5}\n'
        "2024-01-01 12:00:01 UTC [2]: LOG:  duration: 0.05 ms  plan:\n"
        '        {"Plan": {"Node Type": "Index Scan", "Relation Name": "customers", '
        '"Actual Total Time": 0.03, "Actual Rows": 1}, "Execution Time": 0.05}\n'
    )
    r = client.post("/api/v1/analyze/batch", json={"log_text": log_text})
    assert r.status_code == 200
    body = r.json()
    assert body["entries_found"] == 2
    assert len(body["results"]) == 2
    assert body["parse_errors"] == []
    # sorted by runtime descending
    assert body["results"][0]["total_runtime_ms"] >= body["results"][1]["total_runtime_ms"]


def test_analyze_batch_reports_parse_errors_without_failing_whole_request(client):
    log_text = (
        "2024-01-01 12:00:00 UTC [1]: LOG:  duration: 1.0 ms  plan:\n"
        "        this is not valid EXPLAIN output at all\n"
    )
    r = client.post("/api/v1/analyze/batch", json={"log_text": log_text})
    assert r.status_code == 200
    body = r.json()
    assert body["entries_found"] == 1
    assert body["results"] == []
    assert len(body["parse_errors"]) == 1


def test_analyze_batch_empty_log_returns_no_entries(client):
    r = client.post("/api/v1/analyze/batch", json={"log_text": "nothing interesting here"})
    assert r.status_code == 200
    body = r.json()
    assert body["entries_found"] == 0
    assert body["results"] == []


def test_analyze_batch_rejects_too_many_entries(client, monkeypatch):
    monkeypatch.setenv("PGPA_MAX_BATCH_ENTRIES", "2")
    from app.config import get_settings, get_thresholds

    get_settings.cache_clear()
    get_thresholds.cache_clear()

    entry = (
        "2024-01-01 12:00:00 UTC [1]: LOG:  duration: 1.0 ms  plan:\n"
        '        {"Plan": {"Node Type": "Index Scan", "Relation Name": "t"}, "Execution Time": 1.0}\n'
    )
    log_text = entry * 3

    r = client.post("/api/v1/analyze/batch", json={"log_text": log_text})
    assert r.status_code == 413

    get_settings.cache_clear()
    get_thresholds.cache_clear()
