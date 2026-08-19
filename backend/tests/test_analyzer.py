
from app.analyzer.engine import analyze


def test_seq_scan_finding():
    plan = {
        "Plan": {
            "Node Type": "Seq Scan",
            "Relation Name": "orders",
            "Plan Rows": 100,
            "Actual Rows": 50000,
            "Actual Total Time": 900,
            "Rows Removed by Filter": 100000,
            "Shared Read Blocks": 12000
        },
        "Execution Time": 1000
    }
    result = analyze(plan)
    assert result.app_name == "pgPlanAdvisor"
    assert result.top_findings
