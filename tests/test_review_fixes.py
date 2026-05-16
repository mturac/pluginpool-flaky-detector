"""Regression tests for flaky-detector review findings."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import flaky  # noqa: E402


def test_aggregate_imputes_missing_runs_as_pass():
    """A test that fails in run 1 but is absent from run 2 must count as
    pass=1, fail=1 (matching the user-visible behaviour of pytest -q which
    only lists failures). Pre-fix the same test was reported as 100% flaky."""
    runs = [
        {"a::b": "fail"},
        {},  # run 2: pytest -q omits passing tests entirely
    ]
    report = flaky.aggregate(runs)
    rec = next(t for t in report["tests"] if t["id"] == "a::b")
    assert rec["fail_count"] == 1
    assert rec["pass_count"] == 1
    assert rec["flakiness_pct"] == 50.0


def test_aggregate_preserves_old_behaviour_when_disabled():
    runs = [{"a::b": "fail"}, {}]
    report = flaky.aggregate(runs, impute_missing_as_pass=False)
    rec = next(t for t in report["tests"] if t["id"] == "a::b")
    assert rec["fail_count"] == 1
    assert rec["pass_count"] == 0
    assert rec["flakiness_pct"] == 100.0


def test_single_run_does_not_impute():
    """A single run cannot infer "missing means passed"."""
    report = flaky.aggregate([{"a::b": "fail"}])
    rec = next(t for t in report["tests"] if t["id"] == "a::b")
    assert rec["pass_count"] == 0
    assert rec["fail_count"] == 1


def test_unparseable_output_exits_nonzero_with_warning(tmp_path, capsys, monkeypatch):
    """When the parser produces 0 tests across all runs, the script must
    exit non-zero with a warning instead of reporting a clean run
    (review #1 silent false-green finding)."""
    def fake_run_many(cmd, runs, parallel):
        return ["this output does not match any test runner format"] * runs

    monkeypatch.setattr(flaky, "run_many", fake_run_many)
    rc = flaky.main([
        "--cmd", "echo nothing",
        "--runs", "3",
        "--parser", "jest",  # forced parser, will not match the stub output
    ])
    captured = capsys.readouterr()
    assert rc == 3
    payload = json.loads(captured.out)
    assert payload["warnings"]
    assert "0 tests" in payload["warnings"][0]
