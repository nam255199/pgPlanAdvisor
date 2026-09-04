"""Best-effort extraction of column names from EXPLAIN condition strings.

Postgres prints ``Filter``/``Index Cond``/etc. as opaque, already-formatted
SQL fragments, e.g. ``(status = 'shipped'::text AND created_at > '2024-01-01'::date)``.
There's no structured form available - this is a heuristic regex extractor,
not a SQL parser, and is only meant to seed a *suggested* ``CREATE INDEX``
statement for a human to review, never to be trusted blindly.
"""
from __future__ import annotations

import re

# A bare identifier, optionally schema/table-qualified (we only keep the
# last segment - the column name), not immediately preceded by a quote
# (which would mean it's a string literal, not a column reference).
_COLUMN_BEFORE_OP = re.compile(
    r"(?<![\w'\"])([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\s*"
    r"(?:=|<>|!=|<=|>=|<|>|~~|~|\bLIKE\b|\bILIKE\b|\bIN\b)",
    re.IGNORECASE,
)

# Words that are SQL keywords/functions, not column names, and would
# otherwise be picked up by the regex above (e.g. "AND x = 1").
_STOPWORDS = {
    "and",
    "or",
    "not",
    "any",
    "all",
    "null",
    "true",
    "false",
    "coalesce",
    "lower",
    "upper",
    "cast",
}


def extract_columns(condition: str | None) -> list[str]:
    """Pull likely column names out of a Postgres-formatted condition string.

    Returns a deduplicated list, in first-seen order. Best-effort: skips
    anything that looks like a keyword/function rather than a bare column
    reference. Callers should treat the result as a *suggestion*, not a
    verified fact.
    """
    if not condition:
        return []

    # Condition strings from rules/helpers.condition() are prefixed with
    # "Index Cond: " / "Filter: " etc. - strip that if present.
    if ": " in condition and condition.split(": ", 1)[0].replace(" ", "").isalpha():
        condition = condition.split(": ", 1)[1]

    columns: list[str] = []
    for match in _COLUMN_BEFORE_OP.finditer(condition):
        raw = match.group(1)
        name = raw.rsplit(".", 1)[-1]
        if name.lower() in _STOPWORDS:
            continue
        if name not in columns:
            columns.append(name)
    return columns


def suggest_create_index(table: str, condition: str | None) -> str | None:
    """Return a ``CREATE INDEX ...`` suggestion for ``table``, or None if no
    usable column could be extracted from ``condition``."""
    columns = extract_columns(condition)
    if not columns or not table:
        return None
    cols = ", ".join(columns)
    return f"CREATE INDEX ON {table} ({cols});  -- unverified, review before running"
