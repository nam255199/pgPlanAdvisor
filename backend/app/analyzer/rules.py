
from typing import Any, Dict, List
from app.models import Finding
from .walker import walk_plan


def fnum(node: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(node.get(key, default) or default)
    except Exception:
        return default


def relation_name(node: Dict[str, Any]) -> str:
    rel = node.get("Relation Name")
    alias = node.get("Alias")
    idx = node.get("Index Name")
    if rel and alias:
        return f"{rel} {alias}"
    if rel:
        return rel
    if idx:
        return f"index {idx}"
    return "plan node"


def analyze_rules(root: Dict[str, Any], total_runtime_ms: float) -> List[Finding]:
    findings: List[Finding] = []

    for path, parent_id, node in walk_plan(root):
        node_type = node.get("Node Type", "Unknown")
        relation = relation_name(node)
        actual_time = fnum(node, "Actual Total Time")
        actual_rows = fnum(node, "Actual Rows")
        plan_rows = fnum(node, "Plan Rows")
        loops = max(fnum(node, "Actual Loops", 1), 1)
        shared_read = fnum(node, "Shared Read Blocks")
        shared_hit = fnum(node, "Shared Hit Blocks")
        shared_read_time = fnum(node, "Shared Read Time")
        temp_read = fnum(node, "Temp Read Blocks")
        temp_written = fnum(node, "Temp Written Blocks")
        temp_write_time = fnum(node, "Temp Write Time")
        sort_disk = fnum(node, "Sort Disk KB")
        rows_removed = fnum(node, "Rows Removed by Filter")
        score_base = actual_time * loops

        if node_type == "Text EXPLAIN":
            findings.append(Finding(
                severity="info",
                category="Input quality",
                title="Text EXPLAIN detected",
                node_path=path,
                score=1,
                evidence=["Text EXPLAIN was pasted. pgPlanAdvisor parsed table/index names where possible."],
                recommendation="For best accuracy, use EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON).",
                checks=["Re-run with FORMAT JSON when possible.", "Keep BUFFERS enabled."]
            ))

        if "Seq Scan" in node_type and (actual_rows > 1000 or rows_removed > 1000 or score_base > 100 or shared_read > 10000):
            findings.append(Finding(
                severity=_severity(score_base + shared_read_time, total_runtime_ms),
                category="Access path",
                title=f"Sequential scan may be expensive on {relation}",
                node_path=path,
                score=score_base + rows_removed / 1000 + shared_read / 100 + shared_read_time,
                evidence=[
                    f"Node type: {node_type}",
                    f"Relation: {relation}",
                    f"Actual rows: {actual_rows:g}",
                    f"Estimated rows: {plan_rows:g}",
                    f"Rows removed by filter: {rows_removed:g}",
                    f"Actual total time x loops: {score_base:.2f} ms",
                    f"Shared read blocks: {shared_read:g}",
                    f"Shared read time: {shared_read_time:g} ms"
                ],
                recommendation="Verify whether this table scan is expected. If the predicate is selective, check for a suitable index or stale statistics.",
                checks=[
                    f"Inspect table and indexes: \\d+ {relation.split()[0]}",
                    f"Run: ANALYZE {relation.split()[0]};",
                    "Check Filter/Join Filter/Index Cond columns.",
                    "Consider partial/composite/expression indexes if predicates are selective.",
                    "Check table/index bloat and storage latency."
                ]
            ))

        if plan_rows > 0 and actual_rows >= 100:
            ratio = max(actual_rows / plan_rows, plan_rows / max(actual_rows, 1))
            if ratio >= 10:
                findings.append(Finding(
                    severity="high" if ratio >= 100 else "medium",
                    category="Cardinality estimate",
                    title=f"Large row-estimation error on {node_type} ({relation})",
                    node_path=path,
                    score=min(ratio, 1000),
                    evidence=[
                        f"Relation/node: {relation}",
                        f"Estimated rows: {plan_rows:g}",
                        f"Actual rows: {actual_rows:g}",
                        f"Estimate error ratio: {ratio:.1f}x"
                    ],
                    recommendation="Refresh statistics and consider extended statistics for correlated columns.",
                    checks=[
                        f"Run ANALYZE on {relation.split()[0]} if it is a real relation.",
                        "Inspect pg_stats for histogram and MCV quality.",
                        "Consider CREATE STATISTICS for correlated predicates.",
                        "Check expression predicates and data skew."
                    ]
                ))

        if "Sort" in node_type and (temp_read > 0 or temp_written > 0 or sort_disk > 0):
            findings.append(Finding(
                severity="high",
                category="Memory / spill",
                title=f"Sort spilled to disk near {relation}",
                node_path=path,
                score=temp_read + temp_written + sort_disk / 1024 + score_base,
                evidence=[
                    f"Sort method: {node.get('Sort Method', 'unknown')}",
                    f"Sort disk: {sort_disk:g} kB",
                    f"Temp read blocks: {temp_read:g}",
                    f"Temp written blocks: {temp_written:g}",
                    f"Temp write time: {temp_write_time:g} ms"
                ],
                recommendation="This sort is likely a major bottleneck. Consider query/index changes or session-level work_mem testing.",
                checks=[
                    "Check ORDER BY / merge join sort keys.",
                    "Check if an index can provide required order.",
                    "Test higher work_mem only for this query/session.",
                    "Check why upstream rows are much larger than estimated."
                ]
            ))

        if "Hash" in node_type and (temp_read > 0 or temp_written > 0 or fnum(node, "Hash Batches", 1) > 1):
            findings.append(Finding(
                severity="high",
                category="Memory / hash",
                title=f"Hash operation may be memory pressured near {relation}",
                node_path=path,
                score=temp_read + temp_written + score_base,
                evidence=[
                    f"Hash batches: {fnum(node, 'Hash Batches', 0):g}",
                    f"Hash memory: {fnum(node, 'Hash Memory KB', 0):g} kB",
                    f"Temp read blocks: {temp_read:g}",
                    f"Temp written blocks: {temp_written:g}"
                ],
                recommendation="Review hash input size, row estimates, and work_mem.",
                checks=[
                    "Check Batches > 1.",
                    "Check row estimates on hash input.",
                    "Test session-level work_mem.",
                    "Review join keys and possible indexes."
                ]
            ))

        if shared_read > 100000:
            findings.append(Finding(
                severity="high" if shared_read_time > 10000 else "medium",
                category="I/O",
                title=f"Heavy physical reads on {node_type} ({relation})",
                node_path=path,
                score=shared_read / 100 + shared_read_time + score_base,
                evidence=[
                    f"Shared read blocks: {shared_read:g}",
                    f"Shared hit blocks: {shared_hit:g}",
                    f"Shared read time: {shared_read_time:g} ms"
                ],
                recommendation="This node is doing heavy I/O. Check table/index bloat, cache behavior, and whether the access path is appropriate.",
                checks=[
                    f"Check relation size and bloat for {relation.split()[0]}.",
                    "Compare repeated execution after cache warm-up.",
                    "Check storage latency.",
                    "Review index selectivity and correlation."
                ]
            ))

    findings.sort(key=lambda f: f.score, reverse=True)
    return findings


def _severity(score: float, total_runtime_ms: float) -> str:
    if total_runtime_ms and score > total_runtime_ms * 0.25:
        return "high"
    if score > 1000:
        return "high"
    if score > 100:
        return "medium"
    return "low"
