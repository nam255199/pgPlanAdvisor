"""Unit tests calling individual rule functions directly with a hand-built
RuleContext, demonstrating (and locking in) that every rule is a pure,
independently testable function of its input."""
from app.analyzer.context import RuleContext
from app.analyzer.rules.access_path import ineffective_index_scan, seq_scan_expensive
from app.analyzer.rules.memory import sort_spill
from app.config import get_thresholds


def make_ctx(node, **overrides):
    defaults = dict(
        node=node,
        path="Plan",
        node_id="Plan",
        parent_id=None,
        depth=0,
        ancestors=[],
        total_runtime_ms=1000.0,
        planning_time_ms=1.0,
        thresholds=get_thresholds(),
        query=None,
    )
    defaults.update(overrides)
    return RuleContext(**defaults)


def test_seq_scan_expensive_returns_none_for_small_scan():
    node = {"Node Type": "Seq Scan", "Relation Name": "t", "Actual Rows": 5, "Actual Total Time": 0.1}
    assert seq_scan_expensive(make_ctx(node)) is None


def test_seq_scan_expensive_fires_for_large_scan():
    node = {
        "Node Type": "Seq Scan",
        "Relation Name": "t",
        "Actual Rows": 50000,
        "Actual Total Time": 500,
        "Rows Removed by Filter": 100000,
    }
    finding = seq_scan_expensive(make_ctx(node))
    assert finding is not None
    assert finding.rule_id == "seq_scan_expensive"


def test_ineffective_index_scan_ignores_selective_index():
    node = {
        "Node Type": "Index Scan",
        "Relation Name": "t",
        "Filter": "(x = 1)",
        "Actual Rows": 950,
        "Rows Removed by Filter": 10,
    }
    assert ineffective_index_scan(make_ctx(node)) is None


def test_ineffective_index_scan_fires_when_filter_discards_most_rows():
    node = {
        "Node Type": "Index Scan",
        "Relation Name": "t",
        "Filter": "(x = 1)",
        "Actual Rows": 10,
        "Rows Removed by Filter": 4000,
    }
    finding = ineffective_index_scan(make_ctx(node))
    assert finding is not None
    assert finding.rule_id == "ineffective_index_scan"


def test_sort_spill_none_when_in_memory():
    node = {"Node Type": "Sort", "Sort Method": "quicksort", "Actual Total Time": 5}
    assert sort_spill(make_ctx(node)) is None


def test_sort_spill_fires_and_includes_work_mem_suggestion():
    node = {
        "Node Type": "Sort",
        "Sort Method": "external merge",
        "Sort Disk KB": 40960,
        "Actual Total Time": 800,
    }
    finding = sort_spill(make_ctx(node))
    assert finding is not None
    assert "MB" in finding.recommendation
