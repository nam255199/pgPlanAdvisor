"""Command-line entry point for pgPlanAdvisor.

Runs the same rule engine used by the HTTP API directly against a plan
file, with no server required - meant for CI pipelines and shell scripts
that want a pass/fail gate on plan quality or a runtime regression versus
a baseline plan. Installed as the ``pgplanadvisor`` console script (see
``pyproject.toml``).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.analyzer.compare import compare_plans
from app.analyzer.engine import analyze
from app.analyzer.parser import PlanParseError
from app.analyzer.report import to_markdown
from app.config import get_thresholds
from app.models import Severity


def _load_plan(path: str) -> Any:
    text = Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pgplanadvisor",
        description="Analyze a PostgreSQL EXPLAIN plan and optionally gate CI on severity or regressions.",
    )
    parser.add_argument("plan_file", help="Path to an EXPLAIN plan file (JSON or text output).")
    parser.add_argument("--query", default=None, help="Optional SQL text, included for context in the report.")
    parser.add_argument(
        "--baseline", default=None, help="Optional prior EXPLAIN plan file to compare the current plan against."
    )
    parser.add_argument(
        "--fail-on-severity",
        choices=["low", "medium", "high"],
        default="high",
        help="Exit non-zero if any finding at or above this severity is present (default: high).",
    )
    parser.add_argument(
        "--max-regression-pct",
        type=float,
        default=None,
        help="With --baseline, exit non-zero if total runtime increased by more than this percent "
        "(default: the server's compare_regression_pct threshold, 10%%).",
    )
    parser.add_argument("--format", choices=["text", "markdown"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    thresholds = get_thresholds()

    try:
        result = analyze(_load_plan(args.plan_file), args.query, thresholds=thresholds)
    except PlanParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "markdown":
        print(to_markdown(result))
    else:
        print(f"pgPlanAdvisor: {result.summary}")
        print(f"  runtime: {result.total_runtime_ms:.2f} ms  planning: {result.planning_time_ms:.2f} ms")
        for f in result.top_findings:
            print(f"  [{f.severity.value.upper():6}] {f.title} ({f.node_path})")

    exit_code = 0
    threshold_rank = Severity(args.fail_on_severity).rank
    worst_rank = max((f.severity.rank for f in result.top_findings), default=-1)
    if worst_rank >= threshold_rank:
        exit_code = 1

    if args.baseline:
        try:
            baseline_result = analyze(_load_plan(args.baseline), args.query, thresholds=thresholds)
        except PlanParseError as exc:
            print(f"error: could not parse --baseline: {exc}", file=sys.stderr)
            return 2

        comparison = compare_plans(baseline_result, result, thresholds)
        pct_text = f" ({comparison.runtime_delta_pct:+.1f}%)" if comparison.runtime_delta_pct is not None else ""
        print(f"  vs baseline: {comparison.runtime_delta_ms:+.2f} ms{pct_text}")

        max_pct = args.max_regression_pct if args.max_regression_pct is not None else thresholds.compare_regression_pct * 100
        # runtime_delta_pct is None when the baseline's runtime was 0 (e.g.
        # a plan-only baseline with no ANALYZE) - a percentage threshold is
        # meaningless there, but going from an unmeasured baseline to a
        # real runtime is still a regression worth failing on.
        zero_baseline_regression = baseline_result.total_runtime_ms == 0 and result.total_runtime_ms > 0
        pct_regression = comparison.runtime_delta_pct is not None and comparison.runtime_delta_pct > max_pct
        if zero_baseline_regression or pct_regression:
            if zero_baseline_regression and comparison.runtime_delta_pct is None:
                print("  regression: baseline had no measurable runtime (0 ms); current plan does")
            else:
                print(f"  regression: runtime increased {comparison.runtime_delta_pct:.1f}% (limit {max_pct:.1f}%)")
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
