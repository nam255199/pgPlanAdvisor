"""Rules about join strategy: nested loops re-executing an expensive inner
side far too many times (the classic N+1 pattern inside a single plan)."""
from __future__ import annotations

from app.analyzer.context import RuleContext
from app.analyzer.registry import node_rule
from app.models import Finding, Severity

from .helpers import fnum, relation_name


@node_rule
def nested_loop_row_explosion(ctx: RuleContext) -> Finding | None:
    """Flags the *inner* child of a Nested Loop when it is executed many
    times and each execution isn't free. This is the plan-level equivalent
    of an application N+1 query bug."""
    node = ctx.node
    t = ctx.thresholds
    parent = ctx.parent()
    if parent is None or parent.get("Node Type") != "Nested Loop":
        return None

    loops = fnum(node, "Actual Loops", 1)
    per_loop_time = fnum(node, "Actual Total Time")  # per-loop average, per EXPLAIN JSON semantics
    total_time = per_loop_time * loops
    if loops < t.nested_loop_min_loops or total_time < t.nested_loop_min_total_time_ms:
        return None
    relation = relation_name(node)
    node_type = node.get("Node Type", "Unknown")

    return Finding(
        rule_id="nested_loop_row_explosion",
        severity=Severity.HIGH,
        category="Join strategy",
        title=f"Nested Loop re-executes {node_type} on {relation} {loops:g} times",
        node_path=ctx.path,
        score=total_time,
        evidence=[
            f"Loops (outer rows driving this side): {loops:g}",
            f"Average time per execution: {per_loop_time:.3f} ms",
            f"Total time contributed by this side: {total_time:.2f} ms",
        ],
        recommendation=(
            "The inner side of this Nested Loop runs once per outer row. With this many loops, a "
            "Hash Join or Merge Join (or a better index on the inner side) is usually far cheaper."
        ),
        checks=[
            "Check whether an index exists on the inner side's join column.",
            "Check the outer row estimate - if it's wrong, the planner may have chosen Nested Loop "
            "believing there would be few outer rows.",
            "Try SET enable_nestloop = off; on a copy of the query to compare the alternative plan "
            "(diagnostic only, don't leave this set).",
            "Consider rewriting to reduce outer-side cardinality before the join.",
        ],
    )
