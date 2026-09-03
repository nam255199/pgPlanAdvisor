"""Normalizes a SQL query into a stable fingerprint so repeated analyses of
"the same" query (modulo literal values) can be grouped over time, without
needing a real SQL parser."""
from __future__ import annotations

import hashlib
import re

_STRING_LITERAL = re.compile(r"'(?:[^'\\]|\\.)*'")
_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
_WHITESPACE = re.compile(r"\s+")


def fingerprint_query(query: str | None) -> str | None:
    """Return a short, stable hex digest for ``query``, or None if there's
    no query text to fingerprint.

    Two queries that only differ in literal values (numbers, quoted
    strings) normalize to the same fingerprint, so history can group
    repeated runs of the same query shape."""
    if not query or not query.strip():
        return None

    normalized = _STRING_LITERAL.sub("?", query)
    normalized = _NUMBER.sub("?", normalized)
    normalized = _WHITESPACE.sub(" ", normalized).strip().lower()
    if not normalized:
        return None

    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
