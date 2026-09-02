"""Orchestrates parsing, rule evaluation, and response assembly.

This module is intentionally thin: parsing lives in ``parser.py``, plan
traversal in ``walker.py``, and every advisory check lives in ``rules/`` as
an independently-registered rule (see ``registry.py``). ``analyze()`` just
wires those pieces together.
"""
from __future__ import annotations

from typing import Any

from app.config import Thresholds, get_thresholds
from app.models import AnalyzeResponse, Finding, PlanNodeSummary

# Importing app.analyzer.rules registers every built-in rule as a side effect.
from . import rules  # noqa: F401
from .context import PlanContext, RuleContext
from .parser import parse_plan
from .registry import run_node_rules, run_plan_rules
from .walker import flatten_plan, get_root_plan


def _f(node: dict[str, Any], key: str, default: float = 0) -> float:
    try:
        return float(node.get(key) or default)
    except (TypeError, ValueError):
        return default


def _condition(node: dict[str, Any]) -> str | None:
    for key in ("Index Cond", "Filter", "Hash Cond", "Merge Cond", "Join Filter", "Recheck Cond"):
        if node.get(key):
            return f"{key}: {node.get(key)}"
    return None


def analyze(
    raw_plan: Any,
    query: str | None = None,
    thresholds: Thresholds | None = None,
) -> AnalyzeResponse:
    thresholds = thresholds or get_thresholds()

    parsed = parse_plan(raw_plan)
    root = get_root_plan(parsed)
    plan_nodes = flatten_plan(root)

    total_runtime_ms = float(parsed.get("Execution Time") or root.get("Actual Total Time") or 0)
    planning_time_ms = float(parsed.get("Planning Time") or 0)

    by_id = {pn.node_id: pn for pn in plan_nodes}

    def ancestors_of(pn) -> list[dict[str, Any]]:
        chain: list[dict[str, Any]] = []
        parent_id = pn.parent_id
        while parent_id is not None:
            parent = by_id.get(parent_id)
            if parent is None:
                break
            chain.append(parent.node)
            parent_id = parent.parent_id
        chain.reverse()
        return chain

    findings: list[Finding] = []
    node_summaries: list[PlanNodeSummary] = []

    for pn in plan_nodes:
        node = pn.node
        ctx = RuleContext(
            node=node,
            path=pn.path,
            node_id=pn.node_id,
            parent_id=pn.parent_id,
            depth=pn.depth,
            ancestors=ancestors_of(pn),
            total_runtime_ms=total_runtime_ms,
            planning_time_ms=planning_time_ms,
            thresholds=thresholds,
            query=query,
        )
        findings.extend(run_node_rules(ctx))

        actual_time = _f(node, "Actual Total Time")
        loops = _f(node, "Actual Loops", 1)
        node_summaries.append(
            PlanNodeSummary(
                id=pn.node_id,
                parent_id=pn.parent_id,
                path=pn.path,
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
                output=node.get("Output"),
            )
        )

    plan_ctx = PlanContext(
        root=root,
        nodes=plan_nodes,
        total_runtime_ms=total_runtime_ms,
        planning_time_ms=planning_time_ms,
        thresholds=thresholds,
        query=query,
    )
    findings.extend(run_plan_rules(plan_ctx))

    findings.sort(key=lambda f: (f.severity.rank, f.score), reverse=True)

    recommendations: list[str] = []
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
        "Use EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON) when possible.",
    ]

    if not findings:
        summary = "No obvious critical bottleneck detected. Review the visual plan tree and confirm BUFFERS are included."
    else:
        top = findings[0]
        summary = f"Top suspected bottleneck: {top.title}. Severity: {top.severity.value}. {len(findings)} finding(s) detected."

    return AnalyzeResponse(
        app_name="pgPlanAdvisor",
        query=query,
        summary=summary,
        total_runtime_ms=total_runtime_ms,
        planning_time_ms=planning_time_ms,
        top_findings=findings[:12],
        nodes=sorted(node_summaries, key=lambda n: n.bottleneck_score, reverse=True),
        recommendations=recommendations,
        investigation_checklist=checklist,
        normalized_plan=parsed,
    )
