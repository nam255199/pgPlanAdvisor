"""Small shared helpers used across rule modules.

Kept dependency-free (no imports from the registry/context modules) so they
can be unit tested trivially and reused by the report generator too.
"""
from __future__ import annotations

from typing import Any


def fnum(node: dict[str, Any], key: str, default: float = 0.0) -> float:
    """Best-effort float coercion of an EXPLAIN field.

    EXPLAIN JSON output is well-typed, but the text parser and hand-edited
    fixtures sometimes leave strings or ``None`` behind, so this never
    raises.
    """
    try:
        return float(node.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def relation_name(node: dict[str, Any]) -> str:
    rel = node.get("Relation Name")
    alias = node.get("Alias")
    idx = node.get("Index Name")
    if rel and alias and rel != alias:
        return f"{rel} {alias}"
    if rel:
        return rel
    if idx:
        return f"index {idx}"
    return "plan node"

def bare_relation(node: dict[str, Any]) -> str:
    """Just the table name, suitable for dropping into a psql command."""
    rel = node.get("Relation Name")
    return rel if rel else relation_name(node).split()[0]


def condition(node: dict[str, Any]) -> str | None:
    for key in ("Index Cond", "Filter", "Hash Cond", "Merge Cond", "Join Filter", "Recheck Cond"):
        if node.get(key):
            return f"{key}: {node.get(key)}"
    return None


def severity_for_score(score: float, total_runtime_ms: float, thresholds) -> str:
    """Shared severity heuristic: how much of the query's total time (or an
    absolute score) does this finding account for."""
    if total_runtime_ms and score > total_runtime_ms * thresholds.severity_high_fraction_of_runtime:
        return "high"
    if score > thresholds.severity_high_score:
        return "high"
    if score > thresholds.severity_medium_score:
        return "medium"
    return "low"


def suggest_work_mem(spilled_kb: float, safety_factor: float) -> str:
    """Turn an observed disk-spill size into a human suggestion.

    ``work_mem`` bounds memory *per sort/hash node per execution*, so we
    round the observed spill up (with a safety margin for skew and repeat
    executions under concurrency) to the next sensible unit.
    """
    needed_kb = max(spilled_kb, 0) * safety_factor
    needed_mb = needed_kb / 1024
    if needed_mb < 1:
        target = "4MB"
    else:
        # round up to the next 4MB boundary, minimum 4MB
        rounded = max(4, int(-(-needed_mb // 4) * 4))
        target = f"{rounded}MB"
    return target
