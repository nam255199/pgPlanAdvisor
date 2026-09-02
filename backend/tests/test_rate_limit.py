from app.middleware import InMemoryRateLimiter


def test_allows_up_to_the_limit():
    limiter = InMemoryRateLimiter(max_requests=3, window_seconds=60)
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is False


def test_limits_are_independent_per_key():
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-b") is True
    assert limiter.allow("client-a") is False
    assert limiter.allow("client-b") is False


def test_window_resets_hits_over_time(monkeypatch):
    import app.middleware as middleware_module

    fake_now = [1000.0]
    monkeypatch.setattr(middleware_module.time, "monotonic", lambda: fake_now[0])

    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=10)
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is False

    fake_now[0] += 11
    assert limiter.allow("client-a") is True
