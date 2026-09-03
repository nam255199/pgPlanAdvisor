"""Application configuration.

All tunables (thresholds used by the rule engine, security, rate limiting,
persistence, CORS) live here and are overridable via environment variables
prefixed with ``PGPA_``. This keeps ``app.main`` free of magic numbers and
lets operators tune pgPlanAdvisor for their environment without touching
code.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Thresholds(BaseSettings):
    """Numeric thresholds used by advisory rules.

    Every value can be overridden via an environment variable, e.g.
    ``PGPA_SEQ_SCAN_MIN_ROWS=5000``. Keeping these as configuration (rather
    than literals scattered through rule modules) means a DBA can tune
    sensitivity for their workload without forking the analyzer.
    """

    model_config = SettingsConfigDict(env_prefix="PGPA_", extra="ignore")

    # Access path / Seq Scan
    seq_scan_min_rows: float = 1000
    seq_scan_min_rows_removed: float = 1000
    seq_scan_min_score_ms: float = 100
    seq_scan_min_shared_read_blocks: float = 10_000

    # Ineffective index (index scan filtering out most of what it reads)
    index_scan_min_rows_examined: float = 500
    index_scan_max_selectivity_ratio: float = 0.5  # rows_removed / rows_examined

    # Cardinality estimation
    cardinality_min_actual_rows: float = 100
    cardinality_warn_ratio: float = 10
    cardinality_high_ratio: float = 100

    # Memory / spills
    work_mem_safety_factor: float = 1.25  # multiply observed spill by this for the suggestion

    # I/O
    io_heavy_shared_read_blocks: float = 100_000
    io_heavy_read_time_ms: float = 10_000

    # Joins / nested loops. "Total time" is per-loop Actual Total Time
    # multiplied by loop count - EXPLAIN JSON reports the former as a
    # per-execution average, so a cheap-looking node can still dominate
    # runtime once it's re-run thousands of times.
    nested_loop_min_loops: float = 1000
    nested_loop_min_total_time_ms: float = 500

    # Sub-plans / correlated subqueries
    subplan_min_loops: float = 100

    # Parallelism
    parallel_candidate_min_rows: float = 1_000_000
    parallel_candidate_min_time_ms: float = 1000

    # Plan-level buffer cache hit ratio
    cache_hit_ratio_warn: float = 0.90
    cache_hit_ratio_min_blocks: float = 1000  # ignore tiny plans

    # Severity scoring
    severity_high_fraction_of_runtime: float = 0.25
    severity_high_score: float = 1000
    severity_medium_score: float = 100

    # Plan comparison: how much worse (or better) total runtime must be,
    # as a fraction of the baseline, before compare_plans calls it a
    # regression/improvement rather than "unchanged".
    compare_regression_pct: float = 0.10


class Settings(BaseSettings):
    """Top-level service configuration."""

    model_config = SettingsConfigDict(env_prefix="PGPA_", extra="ignore")

    app_name: str = "pgPlanAdvisor"
    app_version: str = "2.0.0"
    environment: str = "development"
    log_level: str = "INFO"
    log_json: bool = False

    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # Security: when unset, the API is open (matches the original project's
    # behavior). Setting PGPA_API_KEY enables auth on mutating/history routes.
    api_key: str | None = None

    # Rate limiting (simple in-memory fixed-window limiter; see app/rate_limit.py)
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # History persistence (SQLite). Disabled by default to keep the service
    # stateless unless an operator opts in.
    history_enabled: bool = False
    history_db_path: str = "./data/pgplanadvisor.db"
    history_max_rows: int = 500

    max_plan_bytes: int = 5_000_000  # reject absurdly large payloads early
    max_batch_entries: int = 200  # cap how many plans /analyze/batch will run per request


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_thresholds() -> Thresholds:
    return Thresholds()
