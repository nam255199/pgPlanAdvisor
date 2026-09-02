"""Meta rule about the quality of the input itself."""
from __future__ import annotations

from app.analyzer.context import RuleContext
from app.analyzer.registry import node_rule
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
