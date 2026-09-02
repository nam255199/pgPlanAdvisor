"""Rules about SubPlan / InitPlan nodes - usually the execution-plan shadow
of a correlated subquery in the SQL text."""
from __future__ import annotations

from app.analyzer.context import RuleContext
from app.analyzer.registry import node_rule
from app.models import Finding, Severity

from .helpers import fnum


@node_rule
def correlated_subquery_repeated(ctx: RuleContext) -> Finding | None:
    node = ctx.node
    t = ctx.thresholds
    node_type = node.get("Node Type", "")
    if node_type not in ("SubPlan", "Subquery Scan") and "Subplan Name" not in node:
        return None

    loops = fnum(node, "Actual Loops", 1)
    if loops < t.subplan_min_loops:
        return None

    actual_time = fnum(node, "Actual Total Time")
    total_time = actual_time * loops
    label = node.get("Subplan Name") or node_type

    return Finding(
        rule_id="correlated_subquery_repeated",
        severity=Severity.MEDIUM if total_time < ctx.total_runtime_ms * 0.1 else Severity.HIGH,
        category="Query shape",
        title=f"{label} executed {loops:g} times",
        node_path=ctx.path,
        score=total_time,
        evidence=[
            f"Executions (loops): {loops:g}",
            f"Average time per execution: {actual_time:.3f} ms",
            f"Total time contributed: {total_time:.2f} ms",
        ],
        recommendation=(
            "This looks like a correlated subquery re-evaluated once per outer row. Rewriting it as "
            "a JOIN or a window function usually lets the planner evaluate it once instead of N times."
        ),
        checks=[
            "Find the correlated subquery in the SQL text (a WHERE ... IN/EXISTS or a scalar "
            "subquery in the SELECT list referencing the outer query).",
            "Try rewriting as a JOIN / LEFT JOIN LATERAL / window function.",
            "If it must stay correlated, check whether an index supports the subquery's own filter.",
        ],
    )
