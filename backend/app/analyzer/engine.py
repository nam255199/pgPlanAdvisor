
from typing import Any
from app.models import AnalyzeResponse, PlanNodeSummary
from .parser import parse_plan
from .walker import get_root_plan, walk_plan
from .rules import analyze_rules


def _f(node, key, default=0):
    try:
        return float(node.get(key) or default)
    except Exception:
        return default


def _condition(node):
    for key in ["Index Cond", "Filter", "Hash Cond", "Merge Cond", "Join Filter", "Recheck Cond"]:
        if node.get(key):
            return f"{key}: {node.get(key)}"
    return None


def analyze(raw_plan: Any, query: str | None = None) -> AnalyzeResponse:
    parsed = parse_plan(raw_plan)
    root = get_root_plan(parsed)

    total_runtime_ms = float(parsed.get("Execution Time") or root.get("Actual Total Time") or 0)
    planning_time_ms = float(parsed.get("Planning Time") or 0)

    findings = analyze_rules(root, total_runtime_ms)
    nodes = []

    for path, parent_id, node in walk_plan(root):
        actual_time = _f(node, "Actual Total Time")
        loops = _f(node, "Actual Loops", 1)
        node_id = path.replace(".", "_").replace("[", "_").replace("]", "")
        nodes.append(PlanNodeSummary(
            id=node_id,
            parent_id=parent_id,
            path=path,
            node_type=node.get("Node Type", "Unknown"),
            relation=node.get("Relation Name"),
            alias=node.get("Alias"),
            index_name=node.get("Index Name"),
            actual_total_time=actual_time,
            actual_rows=_f(node, "Actual Rows"),
            plan_rows=_f(node, "Plan Rows"),
            loops=loops,
            startup_cost=_f(node, "Startup Cost"),
            total_cost=_f(node, "Total Cost"),
            shared_hit_blocks=_f(node, "Shared Hit Blocks"),
            shared_read_blocks=_f(node, "Shared Read Blocks"),
            shared_read_time=_f(node, "Shared Read Time"),
            temp_read_blocks=_f(node, "Temp Read Blocks"),
            temp_written_blocks=_f(node, "Temp Written Blocks"),
            temp_read_time=_f(node, "Temp Read Time"),
            temp_write_time=_f(node, "Temp Write Time"),
            sort_method=node.get("Sort Method"),
            sort_disk_kb=_f(node, "Sort Disk KB"),
            hash_batches=_f(node, "Hash Batches"),
            hash_memory_kb=_f(node, "Hash Memory KB"),
            rows_removed_by_filter=_f(node, "Rows Removed by Filter"),
            bottleneck_score=actual_time * max(loops, 1),
            condition=_condition(node),
            output=node.get("Output")
        ))

    recommendations = []
    for f in findings[:10]:
        if f.recommendation not in recommendations:
            recommendations.append(f.recommendation)

    checklist = [
        "Identify the highest runtime node and its relation/index.",
        "Check whether row estimates differ greatly from actual rows.",
        "Check expensive scans for selective filters without useful indexes.",
        "Check Shared Read Blocks and I/O Timings for storage bottlenecks.",
        "Check Sort Method for external merge / disk spill.",
        "Check Hash Batches and temp blocks for hash spill.",
        "Check Nested Loop loops and the inner child access path.",
        "Run ANALYZE on relations with large estimate errors.",
        "Use EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON) when possible."
    ]

    if not findings:
        summary = "No obvious critical bottleneck detected. Review the visual plan tree and confirm BUFFERS are included."
    else:
        top = findings[0]
        summary = f"Top suspected bottleneck: {top.title}. Severity: {top.severity}. {len(findings)} finding(s) detected."

    return AnalyzeResponse(
        app_name="pgPlanAdvisor",
        summary=summary,
        total_runtime_ms=total_runtime_ms,
        planning_time_ms=planning_time_ms,
        top_findings=findings[:12],
        nodes=sorted(nodes, key=lambda n: n.bottleneck_score, reverse=True),
        recommendations=recommendations,
        investigation_checklist=checklist,
        normalized_plan=parsed
    )
