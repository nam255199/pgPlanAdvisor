"""Cross-cutting HTTP middleware: request correlation IDs and a very small
in-memory rate limiter.

The rate limiter is intentionally simple (fixed-window, per-process, keyed
by client IP): pgPlanAdvisor is a self-hosted internal tool, not a
multi-tenant SaaS, so a Redis-backed limiter would be overkill for most
deployments. If you run multiple backend replicas behind a load balancer,
either enable stickiness or swap this for a shared-store limiter (the
interface is a single ``Limiter`` class you can point at Redis).
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.logging_config import request_id_var


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        token = request_id_var.set(req_id)
        try:
            response: Response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = req_id
        return response


class InMemoryRateLimiter:
    """Fixed-window limiter: N requests per key per window_seconds."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        window_start = now - self.window_seconds
        hits = self._hits[key]
        while hits and hits[0] < window_start:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, limiter: InMemoryRateLimiter, exempt_paths: set[str] | None = None) -> None:
        super().__init__(app)
        self.limiter = limiter
        self.exempt_paths = exempt_paths or {"/health"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        client_key = request.client.host if request.client else "unknown"
        if not self.limiter.allow(client_key):
            return Response(
                content='{"detail": "Rate limit exceeded. Please slow down.", "error_type": "rate_limited"}',
                status_code=429,
                media_type="application/json",
            )
        return await call_next(request)
