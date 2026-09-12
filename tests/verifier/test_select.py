from pathlib import Path

import pytest

from optimizer.verifier.apply import ApplyError
from optimizer.verifier.backup import list_backups
from optimizer.verifier.select import apply_winner, choose_winner, summarize

ORIGINAL = "def f():\n    return 1\n"


def result(cid, accepted, after_ms=None, reason=None, content="x = 1\n", path="lib.py"):
    return {
        "candidate_id": cid,
        "strategy": cid,
        "explanation": "",
        "edits": [{"path": path, "new_content": content}],
        "accepted": accepted,
        "rejection_reason": reason,
        "tests": None,
        "benchmark": {"before_ms": 1000.0, "after_ms": after_ms, "speedup": None}
        if after_ms is not None or reason in (None, "slower", "benchmark_failed")
        else None,
    }


def test_choose_winner_picks_fastest_accepted():
    results = [
        result("candidate_a", True, 400.0),
        result("candidate_b", False, 100.0, reason="tests_failed"),  # fastest but rejected
        result("candidate_c", True, 300.0),
        result("candidate_d", False, 990.0, reason="slower"),
    ]
    assert choose_winner(results)["candidate_id"] == "candidate_c"


def test_choose_winner_none_when_nothing_accepted():
    assert choose_winner([]) is None
    assert choose_winner([result("a", False, reason="apply_failed")]) is None


def test_choose_winner_tie_keeps_first():
    results = [result("candidate_a", True, 300.0), result("candidate_b", True, 300.0)]
    assert choose_winner(results)["candidate_id"] == "candidate_a"


def test_choose_winner_ignores_accepted_without_timing():
    broken = result("candidate_a", True)
    broken["benchmark"] = None
    winner = choose_winner([broken, result("candidate_b", True, 500.0)])
    assert winner["candidate_id"] == "candidate_b"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "lib.py").write_text(ORIGINAL)
    return tmp_path


def test_apply_winner_writes_files_and_leaves_no_backup(project):
    winner = result("candidate_c", True, 300.0, content="def f():\n    return 2\n")

    applied = apply_winner(project, winner)

    assert (project / "lib.py").read_text() == "def f():\n    return 2\n"
    assert applied["candidate_id"] == "candidate_c"
    assert applied["files_changed"] == ["lib.py"]
    assert "+    return 2" in applied["diff"]
    assert list_backups(project) == []


def test_apply_winner_failure_leaves_project_unchanged(project):
    winner = result("candidate_c", True, 300.0, content="def broken(:\n")
    with pytest.raises(ApplyError):
        apply_winner(project, winner)
    assert (project / "lib.py").read_text() == ORIGINAL
    assert list_backups(project) == []


def test_summarize_counts_by_reason():
    results = [
        result("a", True, 400.0),
        result("b", False, reason="tests_failed"),
        result("c", False, reason="tests_failed"),
        result("d", False, 990.0, reason="slower"),
        result("e", True, 300.0),
    ]
    winner = choose_winner(results)
    assert summarize(results, winner) == {
        "attempted": 5,
        "accepted": 2,
        "rejected": {"tests_failed": 2, "slower": 1},
        "winner": "e",
    }
    assert summarize([], None) == {"attempted": 0, "accepted": 0, "rejected": {}, "winner": None}
