from pathlib import Path

import pytest

from optimizer.verifier.apply import ApplyError, apply_candidate, edits_of
from optimizer.verifier.backup import discard, list_backups, restore

ORIGINAL = "def get_user(users, uid):\n    return [u for u in users if u.id == uid][0]\n"
FASTER = "def get_user(users, uid):\n    return users[uid]\n"


def cand(*edits, cid="candidate_a"):
    return {
        "candidate_id": cid,
        "strategy": "index lookup",
        "explanation": "O(1) instead of O(n)",
        "edits": [{"path": p, "new_content": c} for p, c in edits],
    }


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "users.py").write_text(ORIGINAL)
    return tmp_path


def test_apply_writes_files_and_returns_restorable_snapshot(project):
    snap = apply_candidate(project, cand(("services/users.py", FASTER)))

    assert (project / "services" / "users.py").read_text() == FASTER
    assert [f["path"] for f in snap["files"]] == ["services/users.py"]

    restore(snap)
    assert (project / "services" / "users.py").read_text() == ORIGINAL


def test_apply_creates_new_files_with_parent_dirs(project):
    snap = apply_candidate(project, cand(("services/cache/store.py", "CACHE = {}\n")))
    assert (project / "services" / "cache" / "store.py").read_text() == "CACHE = {}\n"

    restore(snap)
    assert not (project / "services" / "cache" / "store.py").exists()


def test_discard_keeps_applied_changes(project):
    snap = apply_candidate(project, cand(("services/users.py", FASTER)))
    discard(snap)
    assert (project / "services" / "users.py").read_text() == FASTER
    assert list_backups(project) == []


def test_edits_of_reads_agreed_schema():
    pairs = edits_of(cand(("a.py", "1\n"), ("b/c.py", "2\n")))
    assert pairs == [("a.py", "1\n"), ("b/c.py", "2\n")]


@pytest.mark.parametrize(
    "bad, message",
    [
        ("not a dict", "must be a dict"),
        ({"candidate_id": "x"}, "no edits"),
        ({"candidate_id": "x", "edits": []}, "no edits"),
        ({"edits": [{"path": f"f{i}.py", "new_content": ""} for i in range(4)]}, "max 3"),
        ({"edits": ["nope"]}, "not a dict"),
        ({"edits": [{"new_content": "x"}]}, "no path"),
        ({"edits": [{"path": "a.py"}]}, "no new_content"),
        ({"edits": [{"path": "/etc/passwd", "new_content": "x"}]}, "must be relative"),
        ({"edits": [{"path": "a.py", "new_content": "1"}, {"path": "a.py", "new_content": "2"}]}, "duplicate"),
    ],
)
def test_edits_of_rejects_malformed_candidates(bad, message):
    with pytest.raises(ApplyError, match=message):
        edits_of(bad)


def test_syntax_error_is_rejected_before_touching_disk(project):
    with pytest.raises(ApplyError, match="syntax error in services/users.py line 1"):
        apply_candidate(project, cand(("services/users.py", "def broken(:\n")))

    assert (project / "services" / "users.py").read_text() == ORIGINAL
    assert list_backups(project) == []


def test_non_python_files_are_not_syntax_checked(project):
    snap = apply_candidate(project, cand(("config.txt", "this is (not python\n")))
    assert (project / "config.txt").read_text() == "this is (not python\n"
    discard(snap)


def test_path_outside_root_is_rejected(project):
    with pytest.raises(ApplyError, match="outside the project root"):
        apply_candidate(project, cand(("../escape.py", "x = 1\n")))
    assert not (project.parent / "escape.py").exists()


def test_partial_write_failure_rolls_everything_back(project):
    # Second edit targets a path whose parent is an existing *file*, so mkdir/write fails.
    (project / "blocker").write_text("i am a file")
    c = cand(("services/users.py", FASTER), ("blocker/inner.py", "x = 1\n"))

    with pytest.raises(ApplyError, match="could not write blocker/inner.py"):
        apply_candidate(project, c)

    assert (project / "services" / "users.py").read_text() == ORIGINAL
    assert (project / "blocker").read_text() == "i am a file"
