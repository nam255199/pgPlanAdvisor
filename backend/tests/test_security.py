from fastapi.testclient import TestClient


def make_client(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    from app.config import get_settings, get_thresholds

    get_settings.cache_clear()
    get_thresholds.cache_clear()
    from app.main import create_app

    return TestClient(create_app())


def test_no_api_key_required_by_default(monkeypatch, fixture):
    client = make_client(monkeypatch)
    r = client.post("/api/v1/analyze", json={"plan": fixture("seq_scan_heavy.json")})
    assert r.status_code == 200


def test_api_key_required_when_configured(monkeypatch, fixture):
    client = make_client(monkeypatch, PGPA_API_KEY="s3cret")
    r = client.post("/api/v1/analyze", json={"plan": fixture("seq_scan_heavy.json")})
    assert r.status_code == 401


def test_correct_api_key_is_accepted(monkeypatch, fixture):
    client = make_client(monkeypatch, PGPA_API_KEY="s3cret")
    r = client.post(
        "/api/v1/analyze",
        json={"plan": fixture("seq_scan_heavy.json")},
        headers={"X-API-Key": "s3cret"},
    )
    assert r.status_code == 200


def test_health_never_requires_api_key(monkeypatch):
    client = make_client(monkeypatch, PGPA_API_KEY="s3cret")
    r = client.get("/health")
    assert r.status_code == 200
