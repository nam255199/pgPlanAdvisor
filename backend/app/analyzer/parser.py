
import json
import re
from typing import Any, Dict, List, Tuple


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


def parse_plan(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        if not raw:
            raise ValueError("Empty plan list")
        return raw[0] if isinstance(raw[0], dict) else {"Plan": raw[0]}

    if not isinstance(raw, str):
        raise ValueError("Unsupported plan format")

    text = raw.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed[0]
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    return parse_text_explain(text)


def parse_text_explain(text: str) -> Dict[str, Any]:
    root = {
        "Plan": {
            "Node Type": "Text EXPLAIN",
            "Raw Text": text,
            "Plans": [],
        },
        "Execution Time": _extract_float(text, r"Execution Time:\s*([0-9.]+)\s*ms"),
        "Planning Time": _extract_float(text, r"Planning Time:\s*([0-9.]+)\s*ms"),
        "Query Identifier": _extract_text(text, r"Query Identifier:\s*([0-9]+)"),
    }

    stack: List[Tuple[int, Dict[str, Any]]] = [(0, root["Plan"])]

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

            parent = stack[-1][1] if stack else root["Plan"]
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


def _parse_node_line(line: str, node_type: str) -> Dict[str, Any]:
    node: Dict[str, Any] = {
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


def _parse_detail_line(line: str) -> Dict[str, Any] | None:
    out: Dict[str, Any] = {}

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
        for metric, key in [
            ("shared hit", "Shared Hit Blocks"),
            ("shared read", "Shared Read Blocks"),
            ("shared dirtied", "Shared Dirtied Blocks"),
            ("shared written", "Shared Written Blocks"),
            ("temp read", "Temp Read Blocks"),
            ("temp written", "Temp Written Blocks"),
            ("local hit", "Local Hit Blocks"),
            ("local read", "Local Read Blocks"),
        ]:
            m = re.search(re.escape(metric) + r"=([0-9.]+)", value)
            if m:
                out[key] = float(m.group(1))
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


def _extract_float(text: str, pattern: str) -> float:
    m = re.search(pattern, text)
    if not m:
        return 0.0
    try:
        return float(m.group(1))
    except Exception:
        return 0.0


def _extract_text(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


def _clean_relation(name: str) -> str:
    return name.strip().strip('"')
