from pathlib import Path

import pytest

from optimizer.verifier.backup import snapshot
from optimizer.verifier.diff import diff_snapshot, diff_stats, render_diff

BEFORE = (
    "for user in users:\n"
    "    if user.id in [x.user_id for x in purchases]:\n"
    "        active.append(user)\n"
)
AFTER = (
    "purchased_user_ids = {x.user_id for x in purchases}\n"
    "\n"
    "for user in users:\n"
    "    if user.id in purchased_user_ids:\n"
    "        active.append(user)\n"
)


def test_render_diff_has_git_headers_and_changed_lines():
    d = render_diff("services/search.py", BEFORE, AFTER)
    lines = d.splitlines()
    assert lines[0] == "--- a/services/search.py"
    assert lines[1] == "+++ b/services/search.py"
    assert "-    if user.id in [x.user_id for x in purchases]:" in lines
    assert "+purchased_user_ids = {x.user_id for x in purchases}" in lines
    assert "+    if user.id in purchased_user_ids:" in lines
    assert d.endswith("\n")


def test_render_diff_identical_is_empty():
    assert render_diff("a.py", "x = 1\n", "x = 1\n") == ""


def test_render_diff_new_and_deleted_files():
    created = render_diff("new.py", "", "x = 1\n")
    assert created.startswith("--- /dev/null\n+++ b/new.py\n")
    deleted = render_diff("old.py", "x = 1\n", "")
    assert deleted.startswith("--- a/old.py\n+++ /dev/null\n")


def test_render_diff_handles_missing_trailing_newline():
    d = render_diff("a.py", "x = 1", "x = 2")
    assert "-x = 1" in d and "+x = 2" in d
    assert d.endswith("\n")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "search.py").write_text(BEFORE)
    (tmp_path / "services" / "users.py").write_text("def get_user(): return 1\n")
    return tmp_path


def test_diff_snapshot_shows_only_changed_files(project):
    snap = snapshot(project, ["services/search.py", "services/users.py", "services/cache.py"])
    (project / "services" / "search.py").write_text(AFTER)
    (project / "services" / "cache.py").write_text("CACHE = {}\n")

    d = diff_snapshot(snap)

    assert "--- a/services/search.py" in d
    assert "+++ b/services/cache.py" in d and "--- /dev/null" in d
    assert "users.py" not in d  # untouched
    # search.py: +purchased line, +blank, -old if, +new if (the `for` line is shared); cache.py: +1
    assert diff_stats(d) == {"files": 2, "added": 4, "removed": 1}


def test_diff_snapshot_no_changes_is_empty(project):
    snap = snapshot(project, ["services/search.py"])
    assert diff_snapshot(snap) == ""
    assert diff_stats("") == {"files": 0, "added": 0, "removed": 0}
