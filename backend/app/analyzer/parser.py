"""Normalizes EXPLAIN output into the plan-JSON shape the rest of the app
expects: ``{"Plan": {...}, "Execution Time": ..., "Planning Time": ...}``.

Accepts, in order of preference:

1. Already-parsed JSON (dict, or a ``[{...}]`` list as psql/JSON output
   produces) - use ``EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)``.
2. A JSON string.
3. Text ``EXPLAIN`` output, on a best-effort basis (see
   ``parse_text_explain``). Field coverage is necessarily narrower than
   JSON, since text EXPLAIN doesn't include everything BUFFERS/VERBOSE add
   to the JSON form in a machine-friendly way.
"""

import json
import re
from typing import Any


class PlanParseError(ValueError):
    """Raised when the input can't be interpreted as an EXPLAIN plan at all."""


NODE_TYPES = [
    "Index Only Scan", "Bitmap Heap Scan", "Bitmap Index Scan",
    "Gather Merge", "Nested Loop", "Hash Left Join", "Hash Right Join", "Hash Full Join",
    "Hash Join", "Merge Left Join", "Merge Right Join", "Merge Full Join", "Merge Join",
    "Seq Scan", "Index Scan", "CTE Scan", "Subquery Scan",
    "Foreign Scan", "Function Scan", "Values Scan",
    "Incremental Sort", "HashAggregate", "GroupAggregate",
    "Memoize", "Materialize", "Sort", "Hash", "Aggregate",
    "Gather", "Limit", "Append", "Merge Append", "Unique",
    "Result", "ProjectSet", "LockRows"
]


def parse_plan(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        if not raw:
            raise PlanParseError("The plan object is empty.")
        return raw
    if isinstance(raw, list):
        if not raw:
            raise PlanParseError("The plan array is empty.")
        return raw[0] if isinstance(raw[0], dict) else {"Plan": raw[0]}

    if not isinstance(raw, str):
        raise PlanParseError(
            f"Unsupported plan payload type: {type(raw).__name__}. Paste EXPLAIN JSON or text output."
        )

    text = raw.strip()
    if not text:
        raise PlanParseError("The plan is empty. Paste EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON) output.")

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            if not parsed:
                raise PlanParseError("The plan array is empty.")
            return parsed[0]
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    plan = parse_text_explain(text)
    if not plan.get("Plan", {}).get("Plans") and plan.get("Plan", {}).get("Node Type") == "Text EXPLAIN":
        # We couldn't recognize a single plan node line - this probably
        # isn't EXPLAIN output at all.
        raise PlanParseError(
            "Could not parse this as EXPLAIN output (no recognizable plan node lines and invalid JSON). "
            "Paste raw EXPLAIN ANALYZE output, ideally with FORMAT JSON."
        )
    return plan


def parse_text_explain(text: str) -> dict[str, Any]:
    root_plan: dict[str, Any] = {
        "Node Type": "Text EXPLAIN",
        "Raw Text": text,
        "Plans": [],
    }
    root: dict[str, Any] = {
        "Plan": root_plan,
        # None (not 0.0) when the line isn't present at all - this is how a
        # plan-only EXPLAIN (no ANALYZE) is distinguished from one that
        # legitimately executed in ~0ms; see has_actual_stats in engine.py.
        "Execution Time": _extract_float(text, r"Execution Time:\s*([0-9.]+)\s*ms"),
        "Planning Time": _extract_float(text, r"Planning Time:\s*([0-9.]+)\s*ms"),
        "Query Identifier": _extract_text(text, r"Query Identifier:\s*([0-9]+)"),
    }

    stack: list[tuple[int, dict[str, Any]]] = [(0, root_plan)]

    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        clean = line[3:].strip() if line.startswith("->") else line

        node_type = _node_type_from_line(clean)
        if node_type:
            node = _parse_node_line(clean, node_type)
            node["Plans"] = []

            while stack and indent <= stack[-1][0]:
                stack.pop()

            parent = stack[-1][1] if stack else root_plan
            parent.setdefault("Plans", []).append(node)
            stack.append((indent, node))
            continue

        detail = _parse_detail_line(clean)
        if detail and stack:
            stack[-1][1].update(detail)

    return root


def _node_type_from_line(line: str) -> str | None:
    for nt in NODE_TYPES:
        if re.search(r"\b" + re.escape(nt) + r"\b", line):
            # Normalize join variants to actual displayed node type where possible.
            return nt
    return None


def _parse_node_line(line: str, node_type: str) -> dict[str, Any]:
    node: dict[str, Any] = {
        "Node Type": node_type,
        "Raw Line": line,
    }

    cost = re.search(r"cost=([0-9.]+)\.\.([0-9.]+)\s+rows=([0-9.]+)\s+width=([0-9.]+)", line)
    if cost:
        node["Startup Cost"] = float(cost.group(1))
        node["Total Cost"] = float(cost.group(2))
        node["Plan Rows"] = float(cost.group(3))
        node["Plan Width"] = float(cost.group(4))

    actual = re.search(r"actual time=([0-9.]+)\.\.([0-9.]+)\s+rows=([0-9.]+)\s+loops=([0-9.]+)", line)
    if actual:
        node["Actual Startup Time"] = float(actual.group(1))
        node["Actual Total Time"] = float(actual.group(2))
        node["Actual Rows"] = float(actual.group(3))
        node["Actual Loops"] = float(actual.group(4))

    # Index Scan using idx on schema.table alias
    m = re.search(r"\b(?:Index Scan|Index Only Scan|Bitmap Index Scan)\s+using\s+([^\s]+)\s+on\s+([^\s\)]+)(?:\s+([^\s\(]+))?", line)
    if m:
        node["Index Name"] = m.group(1)
        node["Relation Name"] = _clean_relation(m.group(2))
        if m.group(3) and not m.group(3).startswith("("):
            node["Alias"] = m.group(3)

    # Seq Scan on schema.table alias
    m = re.search(r"\b(?:Seq Scan|Bitmap Heap Scan|CTE Scan|Subquery Scan|Foreign Scan|Function Scan|Values Scan)\s+on\s+([^\s\)]+)(?:\s+([^\s\(]+))?", line)
    if m:
        node["Relation Name"] = _clean_relation(m.group(1))
        if m.group(2) and not m.group(2).startswith("("):
            node["Alias"] = m.group(2)

    return node


def _parse_detail_line(line: str) -> dict[str, Any] | None:
    out: dict[str, Any] = {}

    detail_map = {
        "Output:": "Output",
        "Filter:": "Filter",
        "Index Cond:": "Index Cond",
        "Recheck Cond:": "Recheck Cond",
        "Hash Cond:": "Hash Cond",
        "Merge Cond:": "Merge Cond",
        "Join Filter:": "Join Filter",
        "Sort Key:": "Sort Key",
        "Sort Method:": "Sort Method",
        "Group Key:": "Group Key",
    }
    for prefix, key in detail_map.items():
        if line.startswith(prefix):
            value = line[len(prefix):].strip()
            out[key] = value
            if key == "Sort Method":
                disk = re.search(r"Disk:\s*([0-9]+)kB", value)
                mem = re.search(r"Memory:\s*([0-9]+)kB", value)
                if disk:
                    out["Sort Disk KB"] = float(disk.group(1))
                if mem:
                    out["Sort Memory KB"] = float(mem.group(1))
            return out

    m = re.search(r"Rows Removed by Filter:\s*([0-9.]+)", line)
    if m:
        return {"Rows Removed by Filter": float(m.group(1))}

    m = re.search(r"Rows Removed by Join Filter:\s*([0-9.]+)", line)
    if m:
        return {"Rows Removed by Join Filter": float(m.group(1))}

    if line.startswith("Buffers:"):
        value = line[len("Buffers:"):].strip()
        out["Buffers"] = value
        out.update(_parse_buffers_line(value))
        return out

    if line.startswith("I/O Timings:"):
        value = line[len("I/O Timings:"):].strip()
        out["I/O Timings"] = value
        for metric, key in [
            ("shared read", "Shared Read Time"),
            ("shared write", "Shared Write Time"),
            ("temp read", "Temp Read Time"),
            ("temp write", "Temp Write Time"),
        ]:
            m = re.search(re.escape(metric) + r"=([0-9.]+)", value)
            if m:
                out[key] = float(m.group(1))
        return out

    if line.startswith("Buckets:"):
        out["Hash Info"] = line
        m = re.search(r"Batches:\s*([0-9]+)", line)
        if m:
            out["Hash Batches"] = float(m.group(1))
        m = re.search(r"Memory Usage:\s*([0-9]+)kB", line)
        if m:
            out["Hash Memory KB"] = float(m.group(1))
        return out

    if line.startswith("Heap Fetches:"):
        m = re.search(r"Heap Fetches:\s*([0-9.]+)", line)
        return {"Heap Fetches": float(m.group(1)) if m else line}

    return None


_BUFFERS_KEY_MAP = {
    ("shared", "hit"): "Shared Hit Blocks",
    ("shared", "read"): "Shared Read Blocks",
    ("shared", "dirtied"): "Shared Dirtied Blocks",
    ("shared", "written"): "Shared Written Blocks",
    ("local", "hit"): "Local Hit Blocks",
    ("local", "read"): "Local Read Blocks",
    ("local", "dirtied"): "Local Dirtied Blocks",
    ("local", "written"): "Local Written Blocks",
    ("temp", "read"): "Temp Read Blocks",
    ("temp", "written"): "Temp Written Blocks",
}


def _parse_buffers_line(value: str) -> dict[str, float]:
    """Parse Postgres's real ``Buffers:`` format.

    Postgres only writes the ``shared``/``local``/``temp`` qualifier once
    per group, e.g. ``shared hit=500 read=12000, temp read=10 written=10``
    - every ``hit=``/``read=``/``dirtied=``/``written=`` token belongs to
    whichever qualifier most recently appeared. A naive ``"shared
    read="`` substring search (what earlier versions of this parser did)
    silently drops the second-and-later metrics in each group.
    """
    out: dict[str, float] = {}
    qualifier: str | None = None
    for token in re.split(r"[,\s]+", value.strip()):
        if not token:
            continue
        if token in ("shared", "local", "temp"):
            qualifier = token
            continue
        m = re.match(r"(hit|read|dirtied|written)=([0-9.]+)", token)
        if m and qualifier:
            metric, num = m.groups()
            key = _BUFFERS_KEY_MAP.get((qualifier, metric))
            if key:
                out[key] = float(num)
    return out


def _extract_float(text: str, pattern: str) -> float | None:
    m = re.search(pattern, text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _extract_text(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


def _clean_relation(name: str) -> str:
    return name.strip().strip('"')
