import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    path = FIXTURES_DIR / name
    if path.suffix == ".json":
        return json.loads(path.read_text())
    return path.read_text()


@pytest.fixture
def fixture():
    return load_fixture


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Settings/Thresholds are lru_cache'd from env vars; tests that set
    env vars via monkeypatch need a clean slate each time."""
    from app.config import get_settings, get_thresholds

    get_settings.cache_clear()
    get_thresholds.cache_clear()
    yield
    get_settings.cache_clear()
    get_thresholds.cache_clear()
