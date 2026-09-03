"""Splits captured ``auto_explain`` log output into individual plan bodies.

With ``auto_explain.log_min_duration`` and ``log_analyze`` enabled, Postgres
logs a line like::

    duration: 123.456 ms  plan:
            {
              "Plan": { ... }
            }

(or the equivalent indented text-EXPLAIN form when ``log_format=text``) once
per slow statement. This lets a batch of captured entries from a log file be
analyzed together instead of copy-pasting one plan at a time. The actual
plan body (JSON or text) is handed off to the existing ``parser.parse_plan``
- this module's only job is finding where each entry starts and ends.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_DURATION_MARKER = re.compile(r"duration:\s*([\d.]+)\s*ms\s*plan:\s*$", re.IGNORECASE)


@dataclass
class LogPlanEntry:
    duration_ms: float
    raw_text: str
    line_number: int


def extract_plans_from_log(log_text: str) -> list[LogPlanEntry]:
    """Best-effort split of ``log_text`` into one entry per logged plan.

    A continuation line is any line indented with leading whitespace
    (both JSON and text EXPLAIN bodies are logged that way); the block
    ends at the next duration marker or the first un-indented line.
    """
    lines = log_text.splitlines()
    entries: list[LogPlanEntry] = []
    i = 0
    n = len(lines)
    while i < n:
        match = _DURATION_MARKER.search(lines[i])
        if not match:
            i += 1
            continue

        duration_ms = float(match.group(1))
        start_line = i + 2  # 1-indexed line number of the plan body's first line
        i += 1
        block: list[str] = []
        while i < n and lines[i][:1] in (" ", "\t") and not _DURATION_MARKER.search(lines[i]):
            block.append(lines[i])
            i += 1

        raw_text = "\n".join(block).strip()
        if raw_text:
            entries.append(LogPlanEntry(duration_ms=duration_ms, raw_text=raw_text, line_number=start_line))

    return entries
