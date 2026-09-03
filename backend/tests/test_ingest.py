from app.analyzer.ingest import extract_plans_from_log
from app.analyzer.parser import parse_plan

LOG_TEXT = """\
2024-01-01 12:00:00.123 UTC [12345]: LOG:  duration: 123.456 ms  plan:
        {
          "Plan": {
            "Node Type": "Seq Scan",
            "Relation Name": "orders",
            "Actual Total Time": 123.456,
            "Actual Rows": 100
          },
          "Execution Time": 123.456
        }
2024-01-01 12:00:01.456 UTC [12346]: LOG:  duration: 45.0 ms  plan:
        {
          "Plan": {
            "Node Type": "Index Scan",
            "Relation Name": "customers",
            "Actual Total Time": 45.0
          },
          "Execution Time": 45.0
        }
2024-01-01 12:00:02.000 UTC [12347]: LOG:  connection received
"""


def test_extract_plans_from_log_finds_both_entries():
    entries = extract_plans_from_log(LOG_TEXT)
    assert len(entries) == 2
    assert entries[0].duration_ms == 123.456
    assert entries[1].duration_ms == 45.0


def test_extract_plans_from_log_bodies_are_parseable():
    entries = extract_plans_from_log(LOG_TEXT)
    plan = parse_plan(entries[0].raw_text)
    assert plan["Plan"]["Node Type"] == "Seq Scan"
    assert plan["Plan"]["Relation Name"] == "orders"


def test_extract_plans_from_log_ignores_unrelated_lines():
    entries = extract_plans_from_log("just some log noise\nwith no duration markers\n")
    assert entries == []


def test_extract_plans_from_log_empty_text():
    assert extract_plans_from_log("") == []
