"""Structural before/after comparison between two already-analyzed plans.

Matches plan nodes by ``path`` (e.g. ``Plan.Plans[0]``), which is the right
notion of "the same node" when comparing two runs of the same query shape
(before/after an index change, a config tweak, or a deploy) - the common
case this is built for. A plan whose *shape* changed between runs will show
those nodes as added/removed rather than mismatched.
"""
from __future__ import annotations

from app.config import Thresholds
from app.models import AnalyzeResponse, CompareResponse, Finding, NodeDelta, PlanNodeSummary


def _pct_delta(baseline: float, current: float) -> float | None:
    if baseline == 0:
        return None
    return (current - baseline) / baseline * 100


def _node_delta(baseline: PlanNodeSummary | None, current: PlanNodeSummary | None) -> NodeDelta:
    if baseline is not None and current is not None:
        return NodeDelta(
            path=current.path,
            node_type=current.node_type,
            relation=current.relation,
            status="matched",
            baseline_time_ms=baseline.actual_total_time,
            current_time_ms=current.actual_total_time,
            time_delta_ms=current.actual_total_time - baseline.actual_total_time,
            time_delta_pct=_pct_delta(baseline.actual_total_time, current.actual_total_time),
            baseline_rows=baseline.actual_rows,
            current_rows=current.actual_rows,
            rows_delta_pct=_pct_delta(baseline.actual_rows, current.actual_rows),
        )
    if current is not None:
        return NodeDelta(
            path=current.path,
            node_type=current.node_type,
            relation=current.relation,
            status="added",
            current_time_ms=current.actual_total_time,
            current_rows=current.actual_rows,
        )
    assert baseline is not None
    return NodeDelta(
        path=baseline.path,
        node_type=baseline.node_type,
        relation=baseline.relation,
        status="removed",
        baseline_time_ms=baseline.actual_total_time,
        baseline_rows=baseline.actual_rows,
    )


def _sort_key(delta: NodeDelta) -> float:
    if delta.time_delta_ms is not None:
        return abs(delta.time_delta_ms)
    return delta.current_time_ms or delta.baseline_time_ms or 0


def _verdict(baseline_ms: float, current_ms: float, delta_pct: float | None, regression_pct: float) -> str:
    if baseline_ms == 0:
        # delta_pct is mathematically undefined (division by zero) here,
        # not "no change" - going from an unmeasured/zero baseline to a
        # real runtime is a regression, not silence.
        return "regressed" if current_ms > 0 else "unchanged"
    if delta_pct is not None and delta_pct > regression_pct:
        return "regressed"
    if delta_pct is not None and delta_pct < -regression_pct:
        return "improved"
    return "unchanged"


def compare_plans(
    baseline: AnalyzeResponse, current: AnalyzeResponse, thresholds: Thresholds
) -> CompareResponse:
    baseline_by_path = {n.path: n for n in baseline.nodes}
    current_by_path = {n.path: n for n in current.nodes}
    all_paths = sorted(set(baseline_by_path) | set(current_by_path))

    node_deltas = [_node_delta(baseline_by_path.get(p), current_by_path.get(p)) for p in all_paths]
    node_deltas.sort(key=_sort_key, reverse=True)

    runtime_delta_ms = current.total_runtime_ms - baseline.total_runtime_ms
    runtime_delta_pct = _pct_delta(baseline.total_runtime_ms, current.total_runtime_ms)

    # Findings diff is scoped to top_findings (the top 12 by severity/score
    # on each side) rather than every finding the engine produced - that's
    # what both AnalyzeResponses actually expose, and it's exactly the set
    # a human reviewing either report would see.
    def _key(f: Finding) -> tuple[str, str]:
        return (f.rule_id, f.node_path)

    baseline_findings = {_key(f): f for f in baseline.top_findings}
    current_findings = {_key(f): f for f in current.top_findings}
    findings_added = [f for key, f in current_findings.items() if key not in baseline_findings]
    findings_resolved = [f for key, f in baseline_findings.items() if key not in current_findings]

    verdict = _verdict(
        baseline.total_runtime_ms, current.total_runtime_ms, runtime_delta_pct, thresholds.compare_regression_pct * 100
    )

    return CompareResponse(
        baseline=baseline,
        current=current,
        runtime_delta_ms=runtime_delta_ms,
        runtime_delta_pct=runtime_delta_pct,
        verdict=verdict,
        node_deltas=node_deltas,
        findings_added=findings_added,
        findings_resolved=findings_resolved,
    )
