"""Meta rules about the quality of the input itself."""
from __future__ import annotations

from app.analyzer.context import PlanContext, RuleContext
from app.analyzer.registry import node_rule, plan_rule
from app.models import Finding, Severity


@node_rule
def text_explain_detected(ctx: RuleContext) -> Finding | None:
    if ctx.node.get("Node Type") != "Text EXPLAIN":
        return None

    return Finding(
        rule_id="text_explain_detected",
        severity=Severity.INFO,
        category="Input quality",
        title="Text EXPLAIN detected",
        node_path=ctx.path,
        score=1,
        evidence=["Text EXPLAIN was pasted. pgPlanAdvisor parsed table/index names where possible."],
        recommendation="For best accuracy, use EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON).",
        checks=[
            "Re-run with FORMAT JSON when possible - it round-trips exactly, text EXPLAIN parsing is best-effort.",
            "Keep BUFFERS enabled so I/O-related findings are available.",
        ],
    )


@plan_rule
def plan_only_no_analyze(ctx: PlanContext) -> Finding | None:
    """EXPLAIN without ANALYZE carries no actual timing/row/buffer data, so
    almost every other rule (which compares actual vs. estimated numbers)
    silently finds nothing - not because the plan is healthy, but because
    there's no execution evidence to evaluate. Flag that distinction
    explicitly instead of letting a quiet report look like a clean bill of
    health."""
    if ctx.has_actual_stats:
        return None

    return Finding(
        rule_id="plan_only_no_analyze",
        severity=Severity.INFO,
        category="Input quality",
        title="This is an estimate-only plan (no ANALYZE)",
        node_path="Plan",
        score=1,
        evidence=[
            "No 'Actual Total Time'/'Execution Time' fields were present in the input.",
            "Timing, row-count, spill, and I/O based findings all rely on actual execution "
            "stats and were effectively skipped for this plan.",
        ],
        recommendation=(
            "Re-run with EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) to get real timing, row, and "
            "buffer numbers - a plan-only EXPLAIN can only show cost estimates, which is a much "
            "weaker signal for finding the actual bottleneck."
        ),
        checks=[
            "Only run EXPLAIN ANALYZE against a query you're comfortable actually executing "
            "(it runs the query for real, including any writes).",
        ],
    )
