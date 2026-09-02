"""Physical I/O rules."""
from __future__ import annotations

from app.analyzer.context import RuleContext
from app.analyzer.registry import node_rule
from app.models import Finding, Severity

from .helpers import bare_relation, fnum, relation_name


@node_rule
def heavy_physical_io(ctx: RuleContext) -> Finding | None:
    node = ctx.node
    t = ctx.thresholds
    shared_read = fnum(node, "Shared Read Blocks")
    if shared_read <= t.io_heavy_shared_read_blocks:
        return None

    node_type = node.get("Node Type", "Unknown")
    relation = relation_name(node)
    table = bare_relation(node)
    shared_hit = fnum(node, "Shared Hit Blocks")
    shared_read_time = fnum(node, "Shared Read Time")
    actual_time = fnum(node, "Actual Total Time")
    loops = max(fnum(node, "Actual Loops", 1), 1)
    score_base = actual_time * loops

    return Finding(
        rule_id="heavy_physical_io",
        severity=Severity.HIGH if shared_read_time > t.io_heavy_read_time_ms else Severity.MEDIUM,
        category="I/O",
        title=f"Heavy physical reads on {node_type} ({relation})",
        node_path=ctx.path,
        score=shared_read / 100 + shared_read_time + score_base,
        evidence=[
            f"Shared read blocks: {shared_read:g}",
            f"Shared hit blocks: {shared_hit:g}",
            f"Shared read time: {shared_read_time:g} ms",
        ],
        recommendation=(
            "This node is doing heavy I/O. Check table/index bloat, cache behavior, and whether the "
            "access path is appropriate."
        ),
        checks=[
            f"Check relation size and bloat for {table}: SELECT pg_size_pretty(pg_total_relation_size('{table}'));",
            "Compare repeated execution after cache warm-up (cold vs warm cache).",
            "Check storage latency (iostat / cloud volume metrics) if shared read time is high.",
            "Review index selectivity and correlation with physical row order.",
        ],
    )
