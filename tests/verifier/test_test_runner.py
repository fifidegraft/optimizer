import shlex
import sys
from pathlib import Path

import pytest

from optimizer.verifier.test_runner import parse_pytest_summary, run_tests

PY = shlex.quote(sys.executable)


def test_no_command_is_skipped_and_passes(tmp_path):
    for cmd in (None, "", "   "):
        r = run_tests(cmd, tmp_path)
        assert r["passed"] is True
        assert r["skipped"] is True
        assert r["exit_code"] == 0


def test_exit_zero_passes(tmp_path):
    r = run_tests(f'{PY} -c "print(\'ok\')"', tmp_path)
    assert r["passed"] is True
    assert r["skipped"] is False
    assert r["exit_code"] == 0
    assert "ok" in r["output"]
    assert r["duration_ms"] > 0


def test_nonzero_exit_fails_without_raising(tmp_path):
    r = run_tests(f'{PY} -c "import sys; print(\'boom\'); sys.exit(3)"', tmp_path)
    assert r["passed"] is False
    assert r["exit_code"] == 3
    assert "boom" in r["output"]


def test_runs_in_given_cwd(tmp_path):
    (tmp_path / "marker.txt").write_text("here")
    r = run_tests(f'{PY} -c "print(open(\'marker.txt\').read())"', tmp_path)
    assert r["passed"] and "here" in r["output"]


def test_missing_cwd_raises(tmp_path):
    with pytest.raises(NotADirectoryError):
        run_tests("true", tmp_path / "nope")


def test_timeout_is_a_failure_not_an_exception(tmp_path):
    r = run_tests(f'{PY} -c "import time; time.sleep(5)"', tmp_path, timeout=0.5)
    assert r["passed"] is False
    assert r["timed_out"] is True
    assert "timed out" in r["output"]


def test_output_is_truncated_to_tail(tmp_path):
    r = run_tests(f'{PY} -c "print(\'x\' * 20000); print(\'END\')"', tmp_path)
    assert len(r["output"]) <= 10_000
    assert r["output"].rstrip().endswith("END")


@pytest.mark.parametrize(
    "line, expected",
    [
        ("======= 34 passed in 0.51s =======", (34, 34, 0)),
        ("===== 2 failed, 32 passed in 1.23s =====", (34, 32, 2)),
        ("== 1 failed, 5 passed, 2 skipped, 1 error in 0.1s ==", (7, 5, 2)),
        ("=== 3 passed, 1 xfailed in 0.2s ===", (3, 3, 0)),
        ("1 failed, 2 passed in 0.03s", (3, 2, 1)),  # pytest -q has no bars
        ("34 passed, 1 warning in 0.51s", (34, 34, 0)),
        ("2 passed in 0.10s (0:00:00)", (2, 2, 0)),  # --durations style suffix
    ],
)
def test_parse_pytest_summary(line, expected):
    noise = "some earlier output\nFAILED tests/test_x.py::test_y\n"
    c = parse_pytest_summary(noise + line + "\n")
    assert (c["total"], c["passed_count"], c["failed"]) == expected


def test_parse_pytest_summary_unknown_output():
    c = parse_pytest_summary("not pytest at all\n")
    assert c == {"total": None, "passed_count": None, "failed": None}


def test_real_pytest_run_parses_counts(tmp_path: Path):
    (tmp_path / "test_sample.py").write_text(
        "def test_ok():\n    assert True\n\n"
        "def test_ok2():\n    assert 1 + 1 == 2\n\n"
        "def test_bad():\n    assert False\n"
    )
    r = run_tests(f"{PY} -m pytest -q -p no:cacheprovider", tmp_path)
    assert r["passed"] is False
    assert (r["total"], r["passed_count"], r["failed"]) == (3, 2, 1)
