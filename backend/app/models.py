from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        return {"info": 0, "low": 1, "medium": 2, "high": 3}[self.value]


class AnalyzeRequest(BaseModel):
    plan: Any = Field(..., description="PostgreSQL EXPLAIN ANALYZE output: JSON (preferred), or text EXPLAIN.")
    query: str | None = Field(None, description="The SQL statement the plan came from, for context in findings.")
    save: bool = Field(False, description="If history persistence is enabled, save this analysis for later retrieval.")
    label: str | None = Field(None, description="Optional human-readable label to store alongside a saved analysis.")


class Finding(BaseModel):
    rule_id: str = Field(..., description="Stable identifier of the rule that produced this finding, e.g. 'seq_scan_expensive'.")
    severity: Severity
    category: str
    title: str
    node_path: str
    score: float
    evidence: list[str]
    recommendation: str
    checks: list[str] = Field(default_factory=list)


class PlanNodeSummary(BaseModel):
    id: str
    parent_id: str | None = None
    path: str
    node_type: str
    relation: str | None = None
    alias: str | None = None
    index_name: str | None = None
    actual_total_time: float = 0
    actual_rows: float = 0
    plan_rows: float = 0
    loops: float = 1
    startup_cost: float = 0
    total_cost: float = 0
    shared_hit_blocks: float = 0
    shared_read_blocks: float = 0
    shared_read_time: float = 0
    temp_read_blocks: float = 0
    temp_written_blocks: float = 0
    temp_read_time: float = 0
    temp_write_time: float = 0
    sort_method: str | None = None
    sort_disk_kb: float = 0
    hash_batches: float = 0
    hash_memory_kb: float = 0
    rows_removed_by_filter: float = 0
    bottleneck_score: float = 0
    condition: str | None = None
    output: str | None = None


class AnalyzeResponse(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    app_name: str
    app_version: str = "2.0.0"
    label: str | None = None
    query: str | None = None
    summary: str
    total_runtime_ms: float
    planning_time_ms: float
    top_findings: list[Finding]
    nodes: list[PlanNodeSummary]
    recommendations: list[str]
    investigation_checklist: list[str]
    normalized_plan: dict[str, Any]
    saved: bool = False


class HistoryListItem(BaseModel):
    id: str
    created_at: datetime
    label: str | None = None
    summary: str
    total_runtime_ms: float
    top_severity: Severity | None = None
    finding_count: int


class HistoryListResponse(BaseModel):
    items: list[HistoryListItem]
    total: int


class ErrorResponse(BaseModel):
    detail: str
    error_type: str = "analysis_error"
