import pytest

from app.analyzer.parser import PlanParseError, parse_plan


def test_parses_dict_plan(fixture):
    plan = fixture("seq_scan_heavy.json")
    parsed = parse_plan(plan)
    assert parsed["Plan"]["Node Type"] == "Seq Scan"


def test_parses_json_wrapped_in_list(fixture):
    plan = fixture("seq_scan_heavy.json")
    parsed = parse_plan([plan])
    assert parsed["Plan"]["Node Type"] == "Seq Scan"


def test_parses_json_string():
    parsed = parse_plan('{"Plan": {"Node Type": "Seq Scan"}, "Execution Time": 5}')
    assert parsed["Plan"]["Node Type"] == "Seq Scan"
    assert parsed["Execution Time"] == 5


def test_parses_text_explain(fixture):
    text = fixture("text_explain.txt")
    parsed = parse_plan(text)
    root = parsed["Plan"]
    # Text EXPLAIN input is wrapped under a synthetic "Text EXPLAIN" root so
    # a low-severity "prefer FORMAT JSON" finding can be attached to it;
    # the real top-level plan node is its first child.
    assert root["Node Type"] == "Text EXPLAIN"
    top_node = root["Plans"][0]
    assert top_node["Node Type"] == "Nested Loop"
    child_types = [c["Node Type"] for c in top_node["Plans"]]
    assert "Seq Scan" in child_types
    assert "Index Scan" in child_types
    seq_scan = next(c for c in top_node["Plans"] if c["Node Type"] == "Seq Scan")
    assert seq_scan["Relation Name"] == "orders"
    assert seq_scan["Rows Removed by Filter"] == 100000
    assert seq_scan["Shared Read Blocks"] == 12000
    assert parsed["Execution Time"] == pytest.approx(1000.4)
    assert parsed["Planning Time"] == pytest.approx(2.1)


def test_buffers_line_handles_shared_qualifier_grouping():
    from app.analyzer.parser import _parse_buffers_line

    # Real Postgres output only writes "shared"/"temp"/"local" once per
    # group; a naive "shared read=" substring search misses this.
    parsed = _parse_buffers_line("shared hit=500 read=12000, temp read=10 written=20")
    assert parsed["Shared Hit Blocks"] == 500
    assert parsed["Shared Read Blocks"] == 12000
    assert parsed["Temp Read Blocks"] == 10
    assert parsed["Temp Written Blocks"] == 20


def test_empty_string_raises():
    with pytest.raises(PlanParseError):
        parse_plan("   ")


def test_empty_dict_raises():
    with pytest.raises(PlanParseError):
        parse_plan({})


def test_empty_list_raises():
    with pytest.raises(PlanParseError):
        parse_plan([])


def test_garbage_text_raises():
    with pytest.raises(PlanParseError):
        parse_plan("this is not an explain plan at all, just some prose.")


def test_unsupported_type_raises():
    with pytest.raises(PlanParseError):
        parse_plan(12345)
