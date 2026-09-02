from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_config import setup_logging
from app.middleware import InMemoryRateLimiter, RateLimitMiddleware, RequestIDMiddleware
from app.routes import health_router, router


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_json)

    app = FastAPI(
        title=settings.app_name,
        description=(
            "PostgreSQL EXPLAIN ANALYZE advisor: bottleneck detection via a pluggable rule "
            "engine, plan tree visualization data, and DBA-ready remediation checklists."
        ),
        version=settings.app_version,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)
    if settings.rate_limit_enabled:
        limiter = InMemoryRateLimiter(settings.rate_limit_requests, settings.rate_limit_window_seconds)
        app.add_middleware(RateLimitMiddleware, limiter=limiter)

    app.include_router(health_router)
    app.include_router(router)

    return app


app = create_app()
