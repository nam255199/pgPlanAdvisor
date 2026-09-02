import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def history_client(tmp_path, monkeypatch):
    monkeypatch.setenv("PGPA_HISTORY_ENABLED", "true")
    monkeypatch.setenv("PGPA_HISTORY_DB_PATH", str(tmp_path / "history.db"))
    from app.config import get_settings, get_thresholds

    get_settings.cache_clear()
    get_thresholds.cache_clear()

    from app.main import create_app

    return TestClient(create_app())


def test_save_list_get_delete_roundtrip(history_client, fixture):
    r = history_client.post(
        "/api/v1/analyze",
        json={"plan": fixture("seq_scan_heavy.json"), "save": True, "label": "nightly-batch"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["saved"] is True
    analysis_id = body["id"]

    r = history_client.get("/api/v1/history")
    assert r.status_code == 200
    listing = r.json()
    assert listing["total"] == 1
    assert listing["items"][0]["label"] == "nightly-batch"

    r = history_client.get(f"/api/v1/history/{analysis_id}")
    assert r.status_code == 200
    assert r.json()["id"] == analysis_id

    r = history_client.get(f"/api/v1/history/{analysis_id}/export")
    assert r.status_code == 200
    assert "nightly-batch" in r.text

    r = history_client.delete(f"/api/v1/history/{analysis_id}")
    assert r.status_code == 204

    r = history_client.get(f"/api/v1/history/{analysis_id}")
    assert r.status_code == 404


def test_get_unknown_id_is_404(history_client):
    r = history_client.get("/api/v1/history/does-not-exist")
    assert r.status_code == 404


def test_history_is_bounded_by_max_rows(history_client, fixture, monkeypatch):
    # Re-create with a tiny max_rows to make the trim behavior cheap to test.
    monkeypatch.setenv("PGPA_HISTORY_MAX_ROWS", "2")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    client = TestClient(create_app())

    for i in range(4):
        r = client.post(
            "/api/v1/analyze",
            json={"plan": fixture("seq_scan_heavy.json"), "save": True, "label": f"run-{i}"},
        )
        assert r.status_code == 200

    r = client.get("/api/v1/history")
    assert r.json()["total"] <= 2
