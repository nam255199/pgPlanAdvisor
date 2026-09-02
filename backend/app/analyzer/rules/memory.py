"""Rules about operators spilling to disk because they didn't fit in
work_mem/hash_mem, plus a concrete sizing suggestion for the spill."""
from __future__ import annotations

from app.analyzer.context import RuleContext
from app.analyzer.registry import node_rule
from app.models import Finding, Severity

from .helpers import fnum, relation_name, suggest_work_mem


@node_rule
def sort_spill(ctx: RuleContext) -> Finding | None:
    node = ctx.node
    t = ctx.thresholds
    if "Sort" not in node.get("Node Type", ""):
        return None

    temp_read = fnum(node, "Temp Read Blocks")
    temp_written = fnum(node, "Temp Written Blocks")
    sort_disk = fnum(node, "Sort Disk KB")
    if not (temp_read > 0 or temp_written > 0 or sort_disk > 0):
        return None

    relation = relation_name(node)
    actual_time = fnum(node, "Actual Total Time")
    loops = max(fnum(node, "Actual Loops", 1), 1)
    temp_write_time = fnum(node, "Temp Write Time")
    score_base = actual_time * loops

    spilled_kb = sort_disk if sort_disk > 0 else (temp_read + temp_written) * 8  # 8KB pages
    suggestion = suggest_work_mem(spilled_kb, t.work_mem_safety_factor)

    return Finding(
        rule_id="sort_spill",
        severity=Severity.HIGH,
        category="Memory / spill",
        title=f"Sort spilled to disk near {relation}",
        node_path=ctx.path,
        score=temp_read + temp_written + sort_disk / 1024 + score_base,
        evidence=[
            f"Sort method: {node.get('Sort Method', 'unknown')}",
            f"Sort disk: {sort_disk:g} kB",
            f"Temp read blocks: {temp_read:g}",
            f"Temp written blocks: {temp_written:g}",
            f"Temp write time: {temp_write_time:g} ms",
        ],
        recommendation=(
            "This sort is likely a major bottleneck. Consider query/index changes, or test raising "
            f"work_mem to roughly {suggestion} for this session/query (spilled ~{spilled_kb:.0f} kB)."
        ),
        checks=[
            "Check ORDER BY / merge join sort keys.",
            "Check if an index can provide the required order (avoids the sort entirely).",
            f"Test SET work_mem = '{suggestion}'; for this session/query only, then re-EXPLAIN.",
            "Check why upstream rows are much larger than estimated (a bad estimate causes an "
            "under-sized Sort plan and can hide the real fix, which is upstream).",
        ],
    )


@node_rule
def hash_spill(ctx: RuleContext) -> Finding | None:
    node = ctx.node
    t = ctx.thresholds
    node_type = node.get("Node Type", "")
    if "Hash" not in node_type:
        return None

    temp_read = fnum(node, "Temp Read Blocks")
    temp_written = fnum(node, "Temp Written Blocks")
    batches = fnum(node, "Hash Batches", 1)
    if not (temp_read > 0 or temp_written > 0 or batches > 1):
        return None

    relation = relation_name(node)
    actual_time = fnum(node, "Actual Total Time")
    loops = max(fnum(node, "Actual Loops", 1), 1)
    score_base = actual_time * loops
    hash_memory_kb = fnum(node, "Hash Memory KB")
    spilled_kb = max((temp_read + temp_written) * 8, hash_memory_kb * (batches - 1) if batches > 1 else 0)
    suggestion = suggest_work_mem(spilled_kb, t.work_mem_safety_factor) if spilled_kb else None

    is_aggregate = node_type == "HashAggregate"
    recommendation = "Review hash input size, row estimates, and work_mem."
    if suggestion:
        recommendation += f" Spill implies roughly {suggestion} would have kept this in memory."

    return Finding(
        rule_id="hash_spill",
        severity=Severity.HIGH,
        category="Memory / hash",
        title=(
            f"HashAggregate spilled to disk near {relation}"
            if is_aggregate
            else f"Hash join may be memory pressured near {relation}"
        ),
        node_path=ctx.path,
        score=temp_read + temp_written + score_base,
        evidence=[
            f"Node type: {node_type}",
            f"Hash batches: {batches:g}",
            f"Hash memory: {hash_memory_kb:g} kB",
            f"Temp read blocks: {temp_read:g}",
            f"Temp written blocks: {temp_written:g}",
        ],
        recommendation=recommendation,
        checks=[
            "Check Batches > 1 (means the hash table didn't fit and spilled).",
            "Check row estimates on the hash input side.",
            f"Test SET work_mem = '{suggestion or '64MB'}'; for this session/query, then re-EXPLAIN.",
            "For HashAggregate, check hash_mem_multiplier (PG 13+) which scales aggregate memory "
            "separately from work_mem." if is_aggregate else "Review join keys and possible indexes on the build side.",
        ],
    )
