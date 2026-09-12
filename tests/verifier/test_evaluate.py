import shlex
import sys
from pathlib import Path

import pytest

from optimizer.verifier.backup import list_backups
from optimizer.verifier.evaluate import evaluate_candidate

PY = shlex.quote(sys.executable)

ORIGINAL = "def double(x):\n    return x + x\n"
FASTER = "def double(x):\n    return 2 * x\n"
WRONG = "def double(x):\n    return x\n"

PASS_TESTS = f'{PY} -c "from lib import double; assert double(2) == 4"'


def cand(content, cid="candidate_a", path="lib.py"):
    return {
        "candidate_id": cid,
        "strategy": "multiply",
        "explanation": "one op",
        "edits": [{"path": path, "new_content": content}],
    }


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "lib.py").write_text(ORIGINAL)
    return tmp_path


def fake_benchmark(runtime_ms, exit_code=0):
    """Benchmark stand-in with Person 2's minimal shape."""
    calls = []

    def run(cwd):
        calls.append(Path(cwd))
        return {"runtime_ms": runtime_ms, "exit_code": exit_code, "output": "Runtime: x"}

    run.calls = calls
    return run


def test_faster_candidate_is_accepted_and_project_restored(project):
    bench = fake_benchmark(400.0)
    r = evaluate_candidate(
        project, cand(FASTER), test_command=PASS_TESTS, benchmark=bench, baseline_ms=1000.0
    )

    assert r["accepted"] is True
    assert r["rejection_reason"] is None
    assert r["candidate_id"] == "candidate_a" and r["edits"]  # candidate keys preserved
    assert r["tests"]["passed"] is True
    assert r["benchmark"] == {
        "before_ms": 1000.0,
        "after_ms": 400.0,
        "speedup": 2.5,
        "exit_code": 0,
        "output": "Runtime: x",
    }
    assert "+    return 2 * x" in r["diff"]
    # benchmark ran inside the project, and the project is back to the original
    assert bench.calls == [project]
    assert (project / "lib.py").read_text() == ORIGINAL
    assert list_backups(project) == []


def test_failing_tests_reject_before_benchmark(project):
    bench = fake_benchmark(100.0)
    r = evaluate_candidate(
        project, cand(WRONG), test_command=PASS_TESTS, benchmark=bench, baseline_ms=1000.0
    )

    assert r["accepted"] is False
    assert r["rejection_reason"] == "tests_failed"
    assert r["tests"]["passed"] is False
    assert r["benchmark"] is None
    assert bench.calls == []
    assert (project / "lib.py").read_text() == ORIGINAL
    assert list_backups(project) == []


def test_slower_candidate_is_rejected(project):
    r = evaluate_candidate(
        project,
        cand(FASTER),
        test_command=PASS_TESTS,
        benchmark=fake_benchmark(990.0),
        baseline_ms=1000.0,
    )
    assert r["rejection_reason"] == "slower"
    assert r["tests"]["passed"] is True
    assert r["benchmark"]["after_ms"] == 990.0


def test_min_improvement_threshold(project):
    kwargs = dict(test_command=PASS_TESTS, baseline_ms=1000.0)
    # 3% faster passes the default 2% bar
    assert evaluate_candidate(project, cand(FASTER), benchmark=fake_benchmark(970.0), **kwargs)[
        "accepted"
    ]
    # but not a 5% bar
    assert (
        evaluate_candidate(
            project, cand(FASTER), benchmark=fake_benchmark(970.0), min_improvement=0.05, **kwargs
        )["rejection_reason"]
        == "slower"
    )


def test_benchmark_failure_is_rejected(project):
    r = evaluate_candidate(
        project,
        cand(FASTER),
        test_command=PASS_TESTS,
        benchmark=fake_benchmark(0.0, exit_code=2),
        baseline_ms=1000.0,
    )
    assert r["rejection_reason"] == "benchmark_failed"
    assert r["benchmark"]["after_ms"] is None
    assert r["benchmark"]["speedup"] is None
    assert r["benchmark"]["exit_code"] == 2


def test_apply_failure_runs_nothing(project):
    bench = fake_benchmark(100.0)
    r = evaluate_candidate(
        project,
        cand("def broken(:\n"),
        test_command=PASS_TESTS,
        benchmark=bench,
        baseline_ms=1000.0,
    )
    assert r["rejection_reason"] == "apply_failed"
    assert "syntax error" in r["error"]
    assert r["tests"] is None and r["benchmark"] is None and r["diff"] == ""
    assert bench.calls == []
    assert (project / "lib.py").read_text() == ORIGINAL


def test_no_test_command_skips_straight_to_benchmark(project):
    r = evaluate_candidate(
        project, cand(WRONG), test_command=None, benchmark=fake_benchmark(500.0), baseline_ms=1000.0
    )
    assert r["accepted"] is True
    assert r["tests"]["skipped"] is True


def test_project_restored_even_if_benchmark_raises(project):
    def exploding(cwd):
        raise RuntimeError("profiler crashed")

    with pytest.raises(RuntimeError):
        evaluate_candidate(
            project, cand(FASTER), test_command=PASS_TESTS, benchmark=exploding, baseline_ms=1000.0
        )
    assert (project / "lib.py").read_text() == ORIGINAL
