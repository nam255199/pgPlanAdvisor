from app.analyzer.compare import compare_plans
from app.analyzer.engine import analyze
from app.config import get_thresholds


def test_compare_plans_detects_regression(fixture):
    baseline = analyze(fixture("healthy_plan.json"))
    current = analyze(fixture("seq_scan_heavy.json"))
    comparison = compare_plans(baseline, current, get_thresholds())
    assert comparison.verdict == "regressed"
    assert comparison.runtime_delta_ms > 0


def test_compare_plans_detects_improvement(fixture):
    baseline = analyze(fixture("seq_scan_heavy.json"))
    current = analyze(fixture("healthy_plan.json"))
    comparison = compare_plans(baseline, current, get_thresholds())
    assert comparison.verdict == "improved"
    assert comparison.runtime_delta_ms < 0


def test_compare_plans_unchanged_for_identical_plan(fixture):
    baseline = analyze(fixture("healthy_plan.json"))
    current = analyze(fixture("healthy_plan.json"))
    comparison = compare_plans(baseline, current, get_thresholds())
    assert comparison.verdict == "unchanged"
    assert comparison.runtime_delta_ms == 0


def test_compare_plans_matches_nodes_of_identical_shape(fixture):
    baseline = analyze(fixture("healthy_plan.json"))
    current = analyze(fixture("healthy_plan.json"))
    comparison = compare_plans(baseline, current, get_thresholds())
    assert comparison.node_deltas
    assert all(d.status == "matched" for d in comparison.node_deltas)


def test_compare_plans_reports_new_findings(fixture):
    baseline = analyze(fixture("healthy_plan.json"))
    current = analyze(fixture("seq_scan_heavy.json"))
    comparison = compare_plans(baseline, current, get_thresholds())
    assert any(f.rule_id == "seq_scan_expensive" for f in comparison.findings_added)


def test_compare_plans_zero_baseline_runtime_is_a_regression_not_unchanged():
    # A plan-only (no ANALYZE) baseline has total_runtime_ms == 0, which
    # makes the percentage delta mathematically undefined - that must not
    # be silently read as "no change" when the current plan has a real,
    # positive runtime.
    baseline = analyze({"Plan": {"Node Type": "Seq Scan", "Relation Name": "orders"}})
    current = analyze(
        {"Plan": {"Node Type": "Seq Scan", "Relation Name": "orders", "Actual Total Time": 500.0}, "Execution Time": 500.0}
    )
    assert baseline.total_runtime_ms == 0
    comparison = compare_plans(baseline, current, get_thresholds())
    assert comparison.runtime_delta_pct is None
    assert comparison.verdict == "regressed"


def test_compare_plans_zero_baseline_and_zero_current_is_unchanged():
    baseline = analyze({"Plan": {"Node Type": "Seq Scan", "Relation Name": "orders"}})
    current = analyze({"Plan": {"Node Type": "Seq Scan", "Relation Name": "orders"}})
    comparison = compare_plans(baseline, current, get_thresholds())
    assert comparison.verdict == "unchanged"
