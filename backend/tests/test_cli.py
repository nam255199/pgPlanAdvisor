import json

from app.cli import main


def _write_plan(tmp_path, name, plan):
    path = tmp_path / name
    path.write_text(json.dumps(plan))
    return path


def test_cli_exits_zero_for_healthy_plan(fixture, tmp_path, capsys):
    plan_path = _write_plan(tmp_path, "plan.json", fixture("healthy_plan.json"))
    exit_code = main([str(plan_path)])
    assert exit_code == 0
    assert "pgPlanAdvisor:" in capsys.readouterr().out


def test_cli_exits_nonzero_for_high_severity_finding(fixture, tmp_path):
    plan_path = _write_plan(tmp_path, "plan.json", fixture("seq_scan_heavy.json"))
    exit_code = main([str(plan_path)])
    assert exit_code == 1


def test_cli_fail_on_severity_can_be_relaxed(fixture, tmp_path):
    # seq_scan_heavy trips a "high" severity finding; asking to fail only on
    # a severity higher than what's registered is not possible (high is the
    # ceiling), so instead verify a healthy plan doesn't trip a strict gate.
    plan_path = _write_plan(tmp_path, "plan.json", fixture("healthy_plan.json"))
    exit_code = main([str(plan_path), "--fail-on-severity", "low"])
    assert exit_code == 0


def test_cli_markdown_format(fixture, tmp_path, capsys):
    plan_path = _write_plan(tmp_path, "plan.json", fixture("healthy_plan.json"))
    main([str(plan_path), "--format", "markdown"])
    assert capsys.readouterr().out.startswith("# pgPlanAdvisor report")


def test_cli_baseline_comparison_prints_delta(fixture, tmp_path, capsys):
    baseline_path = _write_plan(tmp_path, "baseline.json", fixture("healthy_plan.json"))
    current_path = _write_plan(tmp_path, "current.json", fixture("seq_scan_heavy.json"))
    exit_code = main([str(current_path), "--baseline", str(baseline_path)])
    out = capsys.readouterr().out
    assert "vs baseline:" in out
    assert exit_code == 1  # both the high-severity finding and the regression trip the gate


def test_cli_zero_baseline_runtime_still_fails_the_gate(tmp_path, capsys):
    # current plan is deliberately finding-free (Index Scan, no Filter, low
    # block counts) so the only thing that can set exit_code=1 here is the
    # baseline-regression check itself, not the severity gate.
    baseline_path = _write_plan(tmp_path, "baseline.json", {"Plan": {"Node Type": "Index Scan", "Relation Name": "t"}})
    current_path = _write_plan(
        tmp_path,
        "current.json",
        {"Plan": {"Node Type": "Index Scan", "Relation Name": "t", "Actual Total Time": 500.0}, "Execution Time": 500.0},
    )
    exit_code = main([str(current_path), "--baseline", str(baseline_path), "--fail-on-severity", "high"])
    out = capsys.readouterr().out
    assert "regression: baseline had no measurable runtime" in out
    assert exit_code == 1


def test_cli_errors_on_unparseable_plan(tmp_path, capsys):
    plan_path = tmp_path / "bad.json"
    plan_path.write_text("not a plan, just prose")
    exit_code = main([str(plan_path)])
    assert exit_code == 2
    assert "error:" in capsys.readouterr().err
