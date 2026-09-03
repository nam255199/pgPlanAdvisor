"""Rules about how a node reads rows from a relation: sequential scans and
index scans that aren't earning their keep."""
from __future__ import annotations

from app.analyzer.context import RuleContext
from app.analyzer.registry import node_rule
from app.models import Finding, Severity

from .helpers import bare_relation, fnum, relation_name, severity_for_score
from .sql_conditions import suggest_create_index


@node_rule
def seq_scan_expensive(ctx: RuleContext) -> Finding | None:
    node = ctx.node
    t = ctx.thresholds
    node_type = node.get("Node Type", "")
    if "Seq Scan" not in node_type:
        return None

    relation = relation_name(node)
    actual_time = fnum(node, "Actual Total Time")
    actual_rows = fnum(node, "Actual Rows")
    plan_rows = fnum(node, "Plan Rows")
    loops = max(fnum(node, "Actual Loops", 1), 1)
    shared_read = fnum(node, "Shared Read Blocks")
    shared_read_time = fnum(node, "Shared Read Time")
    rows_removed = fnum(node, "Rows Removed by Filter")
    score_base = actual_time * loops

    triggered = (
        actual_rows > t.seq_scan_min_rows
        or rows_removed > t.seq_scan_min_rows_removed
        or score_base > t.seq_scan_min_score_ms
        or shared_read > t.seq_scan_min_shared_read_blocks
    )
    if not triggered:
        return None

    score = score_base + rows_removed / 1000 + shared_read / 100 + shared_read_time
    table = bare_relation(node)
    ddl_suggestion = suggest_create_index(table, node.get("Filter"))

    return Finding(
        rule_id="seq_scan_expensive",
        severity=severity_for_score(score + shared_read_time, ctx.total_runtime_ms, t),  # type: ignore[arg-type]
        category="Access path",
        title=f"Sequential scan may be expensive on {relation}",
        node_path=ctx.path,
        score=score,
        ddl_suggestion=ddl_suggestion,
        evidence=[
            f"Node type: {node_type}",
            f"Relation: {relation}",
            f"Actual rows: {actual_rows:g}",
            f"Estimated rows: {plan_rows:g}",
            f"Rows removed by filter: {rows_removed:g}",
            f"Actual total time x loops: {score_base:.2f} ms",
            f"Shared read blocks: {shared_read:g}",
            f"Shared read time: {shared_read_time:g} ms",
        ],
        recommendation=(
            "Verify whether this table scan is expected. If the predicate is selective, "
            "check for a suitable index or stale statistics."
        ),
        checks=[
            f"Inspect table and indexes: \\d+ {table}",
            f"Run: ANALYZE {table};",
            "Check Filter/Join Filter/Index Cond columns.",
            "Consider partial/composite/expression indexes if predicates are selective.",
            "Check table/index bloat and storage latency.",
        ],
    )


@node_rule
def ineffective_index_scan(ctx: RuleContext) -> Finding | None:
    """An Index/Bitmap Index Scan that reads a lot of rows just to discard
    most of them via a Filter is barely better than a Seq Scan - the index
    condition isn't selective enough, or a needed column isn't indexed."""
    node = ctx.node
    t = ctx.thresholds
    node_type = node.get("Node Type", "")
    if node_type not in ("Index Scan", "Index Only Scan", "Bitmap Heap Scan"):
        return None
    if not node.get("Filter"):
        return None

    rows_removed = fnum(node, "Rows Removed by Filter")
    actual_rows = fnum(node, "Actual Rows")
    examined = rows_removed + actual_rows
    if examined < t.index_scan_min_rows_examined:
        return None

    selectivity = rows_removed / examined if examined else 0
    if selectivity < t.index_scan_max_selectivity_ratio:
        return None

    relation = relation_name(node)
    table = bare_relation(node)
    loops = max(fnum(node, "Actual Loops", 1), 1)
    score = rows_removed * loops / 100
    ddl_suggestion = suggest_create_index(table, node.get("Filter"))

    return Finding(
        rule_id="ineffective_index_scan",
        severity=Severity.MEDIUM if selectivity < 0.85 else Severity.HIGH,
        category="Access path",
        title=f"Index on {relation} is filtering out most rows it reads",
        node_path=ctx.path,
        score=score,
        ddl_suggestion=ddl_suggestion,
        evidence=[
            f"Node type: {node_type}",
            f"Index condition selects: {examined:g} rows",
            f"Rows removed by Filter (post-index): {rows_removed:g}",
            f"Rows kept: {actual_rows:g}",
            f"Discard ratio: {selectivity * 100:.1f}%",
            f"Filter: {node.get('Filter')}",
        ],
        recommendation=(
            "The index gets you to the right rows quickly but the residual Filter is doing most "
            "of the work. Consider a composite index that covers the filter predicate too, "
            "or convert the filter into an index condition."
        ),
        checks=[
            f"\\d+ {table}  -- review existing indexes",
            "Check whether the Filter columns can be added to the index (composite/covering index).",
            "Consider a partial index if the filter predicate is a fixed, common value.",
            "Re-check selectivity after ANALYZE if statistics look stale.",
        ],
    )


@node_rule
def missing_parallelism(ctx: RuleContext) -> Finding | None:
    """Large, slow Seq Scans that ran without any parallel workers are worth
    a second look - either the query/session disabled parallelism, or the
    scan is on a parallel-unsafe path (volatile function, etc.)."""
    node = ctx.node
    t = ctx.thresholds
    if "Seq Scan" not in node.get("Node Type", ""):
        return None
    if node.get("Parallel Aware") or node.get("Workers Planned"):
        return None

    actual_rows = fnum(node, "Actual Rows")
    actual_time = fnum(node, "Actual Total Time")
    if actual_rows < t.parallel_candidate_min_rows or actual_time < t.parallel_candidate_min_time_ms:
        return None

    relation = relation_name(node)
    return Finding(
        rule_id="missing_parallelism",
        severity=Severity.LOW,
        category="Parallelism",
        title=f"Large scan on {relation} ran without parallel workers",
        node_path=ctx.path,
        score=actual_time / 100,
        evidence=[
            f"Actual rows: {actual_rows:g}",
            f"Actual total time: {actual_time:.2f} ms",
            "No 'Workers Planned' present on this node.",
        ],
        recommendation=(
            "This scan is large enough that parallel execution could help, but none was used. "
            "Confirm parallel query is actually available for it."
        ),
        checks=[
            "Check max_parallel_workers_per_gather and max_parallel_workers.",
            "Check parallel_setup_cost / parallel_tuple_cost tuning.",
            "Verify no parallel-unsafe function is used in the query (marks the whole plan unsafe).",
            "Check table size vs min_parallel_table_scan_size.",
        ],
    )
