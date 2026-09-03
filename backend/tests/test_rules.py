"""One test module per advisory scenario. These deliberately go through
``engine.analyze()`` end-to-end (parse -> rules -> response) rather than
calling rule functions directly, so they also double as regression tests
for the parser/walker/registry wiring."""
from app.analyzer.engine import analyze


def rule_ids(result):
    return {f.rule_id for f in result.top_findings}


def test_seq_scan_expensive_detected(fixture):
    result = analyze(fixture("seq_scan_heavy.json"))
    assert "seq_scan_expensive" in rule_ids(result)
    finding = next(f for f in result.top_findings if f.rule_id == "seq_scan_expensive")
    assert finding.severity in ("high", "medium")
    assert "orders" in finding.title


def test_sort_spill_detected_with_work_mem_suggestion(fixture):
    result = analyze(fixture("sort_spill.json"))
    assert "sort_spill" in rule_ids(result)
    finding = next(f for f in result.top_findings if f.rule_id == "sort_spill")
    assert finding.severity == "high"
    assert "work_mem" in finding.recommendation


def test_hash_spill_detected(fixture):
    result = analyze(fixture("hash_spill.json"))
    assert "hash_spill" in rule_ids(result)


def test_nested_loop_row_explosion_detected(fixture):
    result = analyze(fixture("nested_loop_explosion.json"))
    assert "nested_loop_row_explosion" in rule_ids(result)
    finding = next(f for f in result.top_findings if f.rule_id == "nested_loop_row_explosion")
    assert finding.severity == "high"
    assert "5000" in " ".join(finding.evidence) or "5,000" in " ".join(finding.evidence)


def test_ineffective_index_scan_detected(fixture):
    result = analyze(fixture("ineffective_index.json"))
    assert "ineffective_index_scan" in rule_ids(result)


def test_subplan_repeated_execution_detected(fixture):
    result = analyze(fixture("subplan_repeated.json"))
    assert "correlated_subquery_repeated" in rule_ids(result)


def test_heavy_physical_io_detected(fixture):
    result = analyze(fixture("heavy_io.json"))
    assert "heavy_physical_io" in rule_ids(result)
    finding = next(f for f in result.top_findings if f.rule_id == "heavy_physical_io")
    assert finding.severity == "high"


def test_low_cache_hit_ratio_detected(fixture):
    result = analyze(fixture("low_cache_hit.json"))
    assert "buffer_cache_hit_ratio" in rule_ids(result)


def test_healthy_plan_has_no_high_severity_findings(fixture):
    result = analyze(fixture("healthy_plan.json"))
    assert all(f.severity != "high" for f in result.top_findings)


def test_findings_are_sorted_by_severity_then_score(fixture):
    result = analyze(fixture("nested_loop_explosion.json"))
    ranks = [f.severity.rank for f in result.top_findings]
    assert ranks == sorted(ranks, reverse=True)


def test_recommendations_are_deduplicated(fixture):
    result = analyze(fixture("seq_scan_heavy.json"))
    assert len(result.recommendations) == len(set(result.recommendations))


def test_every_finding_has_a_rule_id(fixture):
    for name in ["seq_scan_heavy.json", "sort_spill.json", "hash_spill.json", "nested_loop_explosion.json"]:
        result = analyze(fixture(name))
        for f in result.top_findings:
            assert f.rule_id, f"finding without rule_id in {name}: {f}"


def test_seq_scan_expensive_includes_ddl_suggestion(fixture):
    result = analyze(fixture("seq_scan_heavy.json"))
    finding = next(f for f in result.top_findings if f.rule_id == "seq_scan_expensive")
    assert finding.ddl_suggestion is not None
    assert "CREATE INDEX ON orders" in finding.ddl_suggestion
    assert "status" in finding.ddl_suggestion


def test_ineffective_index_scan_includes_ddl_suggestion(fixture):
    result = analyze(fixture("ineffective_index.json"))
    finding = next(f for f in result.top_findings if f.rule_id == "ineffective_index_scan")
    assert finding.ddl_suggestion is not None
    assert "created_at" in finding.ddl_suggestion


def test_plan_only_no_analyze_fires_without_actual_stats():
    plan = {
        "Plan": {
            "Node Type": "Seq Scan",
            "Relation Name": "orders",
            "Plan Rows": 100,
        }
        # No "Actual Total Time" on the root, no top-level "Execution Time":
        # this is what EXPLAIN (without ANALYZE) produces.
    }
    result = analyze(plan)
    assert result.has_actual_stats is False
    assert "plan_only_no_analyze" in rule_ids(result)


def test_plan_only_no_analyze_does_not_fire_with_actual_stats(fixture):
    result = analyze(fixture("healthy_plan.json"))
    assert result.has_actual_stats is True
    assert "plan_only_no_analyze" not in rule_ids(result)


def test_plan_only_no_analyze_fires_for_text_explain_without_analyze():
    # No "actual time=..." on the node line and no "Execution Time:" line -
    # this is what plain `EXPLAIN` (without ANALYZE) text output looks
    # like. parse_text_explain must not default "Execution Time" to 0.0
    # here, or this would be indistinguishable from a plan that really
    # executed in ~0ms.
    text = "Seq Scan on orders  (cost=0.00..1000.00 rows=100 width=50)\n  Filter: (status = 'pending'::text)\n"
    result = analyze(text)
    assert result.has_actual_stats is False
    assert "plan_only_no_analyze" in rule_ids(result)


def test_text_explain_with_analyze_has_actual_stats(fixture):
    result = analyze(fixture("text_explain.txt"))
    assert result.has_actual_stats is True
    assert "plan_only_no_analyze" not in rule_ids(result)
