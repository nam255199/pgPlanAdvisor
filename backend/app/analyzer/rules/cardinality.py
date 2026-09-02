"""Rules about the planner's row estimates being wrong, and why that
matters (it drives every downstream join/method choice)."""
from __future__ import annotations

from app.analyzer.context import PlanContext, RuleContext
from app.analyzer.registry import node_rule, plan_rule
from app.models import Finding, Severity

from .helpers import bare_relation, fnum, relation_name


@node_rule
def cardinality_estimate_error(ctx: RuleContext) -> Finding | None:
    node = ctx.node
    t = ctx.thresholds
    plan_rows = fnum(node, "Plan Rows")
    actual_rows = fnum(node, "Actual Rows")
    if plan_rows <= 0 or actual_rows < t.cardinality_min_actual_rows:
        return None

    ratio = max(actual_rows / plan_rows, plan_rows / max(actual_rows, 1))
    if ratio < t.cardinality_warn_ratio:
        return None

    relation = relation_name(node)
    table = bare_relation(node)
    node_type = node.get("Node Type", "Unknown")
    severity = Severity.HIGH if ratio >= t.cardinality_high_ratio else Severity.MEDIUM

    has_expr_filter = bool(node.get("Filter")) and any(
        token in str(node.get("Filter")) for token in ("::", "(", "COALESCE", "lower(", "upper(")
    )

    recommendation = "Refresh statistics and consider extended statistics for correlated columns."
    if has_expr_filter:
        recommendation += " The filter uses an expression, which plain per-column statistics can't model well."

    checks = [
        f"Run ANALYZE on {table} if it is a real relation.",
        "Inspect pg_stats for histogram and MCV quality: SELECT * FROM pg_stats WHERE tablename = '"
        f"{table}';",
        "Consider CREATE STATISTICS for correlated predicates across multiple columns.",
        "Check expression predicates and data skew.",
    ]
    if has_expr_filter:
        checks.append("Consider an expression index matching the filter expression so the planner can use its statistics.")

    return Finding(
        rule_id="cardinality_estimate_error",
        severity=severity,
        category="Cardinality estimate",
        title=f"Large row-estimation error on {node_type} ({relation})",
        node_path=ctx.path,
        score=min(ratio, 1000),
        evidence=[
            f"Relation/node: {relation}",
            f"Estimated rows: {plan_rows:g}",
            f"Actual rows: {actual_rows:g}",
            f"Estimate error ratio: {ratio:.1f}x",
        ],
        recommendation=recommendation,
        checks=checks,
    )


@plan_rule
def buffer_cache_hit_ratio(ctx: PlanContext) -> Finding | None:
    """Whole-plan buffer cache hit ratio. A single node's read count is
    noisy; the aggregate across the whole plan is a much more reliable
    signal that the working set doesn't fit in shared_buffers / OS cache."""
    t = ctx.thresholds
    total_hit = 0.0
    total_read = 0.0
    for pn in ctx.nodes:
        total_hit += fnum(pn.node, "Shared Hit Blocks")
        total_read += fnum(pn.node, "Shared Read Blocks")

    total = total_hit + total_read
    if total < t.cache_hit_ratio_min_blocks:
        return None

    ratio = total_hit / total
    if ratio >= t.cache_hit_ratio_warn:
        return None

    return Finding(
        rule_id="buffer_cache_hit_ratio",
        severity=Severity.MEDIUM if ratio >= 0.75 else Severity.HIGH,
        category="I/O",
        title="Low shared buffer cache hit ratio across the whole plan",
        node_path="Plan",
        score=(1 - ratio) * 1000,
        evidence=[
            f"Shared hit blocks (sum): {total_hit:g}",
            f"Shared read blocks (sum): {total_read:g}",
            f"Cache hit ratio: {ratio * 100:.1f}%",
        ],
        recommendation=(
            "A large share of this query's blocks came from disk/OS cache rather than "
            "shared_buffers. This is expected on a cold cache, but if consistent across runs it "
            "suggests the working set for this query doesn't fit in memory."
        ),
        checks=[
            "Re-run the query to rule out a cold-cache effect.",
            "Check shared_buffers and effective_cache_size against available RAM.",
            "Check pg_statio_user_tables for this query's relations to see hit ratio over time.",
            "Consider whether the access path can be made more selective (fewer blocks touched).",
        ],
    )
