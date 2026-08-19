
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    plan: Any = Field(..., description="PostgreSQL EXPLAIN ANALYZE output, preferably FORMAT JSON")
    query: Optional[str] = None


class Finding(BaseModel):
    severity: str
    category: str
    title: str
    node_path: str
    score: float
    evidence: List[str]
    recommendation: str
    checks: List[str]


class PlanNodeSummary(BaseModel):
    id: str
    parent_id: Optional[str] = None
    path: str
    node_type: str
    relation: Optional[str] = None
    alias: Optional[str] = None
    index_name: Optional[str] = None
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
    sort_method: Optional[str] = None
    sort_disk_kb: float = 0
    hash_batches: float = 0
    hash_memory_kb: float = 0
    rows_removed_by_filter: float = 0
    bottleneck_score: float = 0
    condition: Optional[str] = None
    output: Optional[str] = None


class AnalyzeResponse(BaseModel):
    app_name: str
    summary: str
    total_runtime_ms: float
    planning_time_ms: float
    top_findings: List[Finding]
    nodes: List[PlanNodeSummary]
    recommendations: List[str]
    investigation_checklist: List[str]
    normalized_plan: Dict[str, Any]
