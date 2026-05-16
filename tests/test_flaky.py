"""Unit tests for flaky.py — parsers, aggregator, exit codes."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "flaky.py"
sys.path.insert(0, str(ROOT / "scripts"))

from flaky import (  # type: ignore  # noqa: E402
    aggregate,
    auto_parser,
    parse_gotest,
    parse_jest,
    parse_pytest,
    parse_tap,
    render_markdown,
)


def test_parse_pytest_short_form_summary():
    """pytest -q only prints `FAILED path::test - reason` in the tail summary."""
    out = (
        "....F.s.                                                            [100%]\n"
        "=================================== FAILURES ===================================\n"
        "________ test_b ________\n"
        "    assert False\n"
        "=========================== short test summary info ============================\n"
        "FAILED tests/test_x.py::test_b - assert False\n"
        "1 failed, 6 passed, 1 skipped in 0.04s\n"
    )
    res = parse_pytest(out)
    assert res.get("tests/test_x.py::test_b") == "fail"


def test_parse_pytest_basic():
    out = (
        "tests/test_a.py::test_one PASSED                       [ 25%]\n"
        "tests/test_a.py::test_two FAILED                       [ 50%]\n"
        "tests/test_b.py::test_three SKIPPED                    [ 75%]\n"
        "tests/test_b.py::test_four PASSED                      [100%]\n"
    )
    res = parse_pytest(out)
    assert res["tests/test_a.py::test_one"] == "pass"
    assert res["tests/test_a.py::test_two"] == "fail"
    assert res["tests/test_b.py::test_three"] == "skip"
    assert res["tests/test_b.py::test_four"] == "pass"


def test_parse_jest():
    out = "  ✓ adds numbers (3 ms)\n  ✗ rejects nan\n  PASS src/util.test.js\n"
    res = parse_jest(out)
    assert res["adds numbers"] == "pass"
    assert res["rejects nan"] == "fail"


def test_parse_gotest():
    out = (
        "=== RUN   TestOne\n"
        "--- PASS: TestOne (0.01s)\n"
        "=== RUN   TestTwo\n"
        "--- FAIL: TestTwo (0.02s)\n"
        "--- SKIP: TestThree (0.00s)\n"
    )
    res = parse_gotest(out)
    assert res == {"TestOne": "pass", "TestTwo": "fail", "TestThree": "skip"}


def test_parse_tap():
    out = "ok 1 - first\nnot ok 2 - second\nok 3\n"
    res = parse_tap(out)
    assert res["first"] == "pass"
    assert res["second"] == "fail"


def test_auto_parser_detection():
    assert auto_parser("pytest -q") == "pytest"
    assert auto_parser("jest --ci") == "jest"
    assert auto_parser("vitest run") == "jest"
    assert auto_parser("go test ./...") == "gotest"
    assert auto_parser("node-tap test/*.js") == "tap"


def test_aggregate_math():
    runs = [
        {"a": "pass", "b": "fail"},
        {"a": "fail", "b": "fail"},
        {"a": "pass", "b": "fail"},
        {"a": "pass", "b": "pass"},
    ]
    rep = aggregate(runs)
    a = next(t for t in rep["tests"] if t["id"] == "a")
    b = next(t for t in rep["tests"] if t["id"] == "b")
    assert a["pass_count"] == 3 and a["fail_count"] == 1
    assert a["flakiness_pct"] == 25.0
    assert b["pass_count"] == 1 and b["fail_count"] == 3
    assert b["flakiness_pct"] == 75.0
    assert rep["summary"]["flaky_tests"] == 2
    assert rep["summary"]["always_failing"] == 0


def test_aggregate_always_failing():
    runs = [{"x": "fail"}, {"x": "fail"}]
    rep = aggregate(runs)
    assert rep["summary"]["always_failing"] == 1
    assert rep["summary"]["flaky_tests"] == 0


def test_render_markdown_hides_always_passing():
    runs = [{"a": "pass", "b": "pass"}, {"a": "pass", "b": "fail"}]
    md = render_markdown(aggregate(runs))
    assert "| a |" not in md     # always-passing hidden
    assert "| b |" in md
    assert "flakiness" in md.lower()


def test_cli_exit_code_warns_when_nothing_parsed(tmp_path):
    """`echo hello` parses to zero tests across all runs — the script must
    surface this as a non-zero exit (was a silent false-green pre-review)."""
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--cmd", "echo hello", "--runs", "2", "--parser", "pytest"],
        capture_output=True, text=True,
    )
    assert r.returncode == 3
    data = json.loads(r.stdout)
    assert data["summary"]["total_runs"] == 2
    assert data["warnings"]


def test_cli_help_works():
    r = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "flaky" in r.stdout.lower()
