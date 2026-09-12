import json
from pathlib import Path

import pytest

from optimizer.verifier import backup
from optimizer.verifier.backup import discard, list_backups, recover_latest, restore, snapshot


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "users.py").write_text("def get_user(): return 1\n")
    (tmp_path / "app.py").write_text("print('hi')\n")
    return tmp_path


def test_snapshot_copies_files_and_writes_manifest(project):
    snap = snapshot(project, ["services/users.py", "app.py"])

    backup_dir = Path(snap["dir"])
    assert backup_dir.is_dir()
    assert (backup_dir / "services" / "users.py").read_text() == "def get_user(): return 1\n"
    assert (backup_dir / "app.py").read_text() == "print('hi')\n"

    manifest = json.loads((backup_dir / "manifest.json").read_text())
    assert manifest == snap
    assert [f["path"] for f in snap["files"]] == ["services/users.py", "app.py"]
    assert all(f["existed"] and f["sha256"] for f in snap["files"])


def test_restore_reverts_modified_files(project):
    snap = snapshot(project, ["services/users.py"])
    (project / "services" / "users.py").write_text("def get_user(): return 'broken'\n")

    touched = restore(snap)

    assert touched == ["services/users.py"]
    assert (project / "services" / "users.py").read_text() == "def get_user(): return 1\n"


def test_restore_deletes_files_created_by_candidate(project):
    snap = snapshot(project, ["services/cache.py"])
    assert snap["files"][0]["existed"] is False

    (project / "services" / "cache.py").write_text("CACHE = {}\n")
    restore(snap)

    assert not (project / "services" / "cache.py").exists()


def test_restore_is_safe_to_call_twice(project):
    snap = snapshot(project, ["app.py", "new.py"])
    (project / "app.py").write_text("changed\n")
    (project / "new.py").write_text("new\n")

    restore(snap)
    restore(snap)

    assert (project / "app.py").read_text() == "print('hi')\n"
    assert not (project / "new.py").exists()


def test_discard_removes_backup_but_keeps_changes(project):
    snap = snapshot(project, ["app.py"])
    (project / "app.py").write_text("faster\n")

    discard(snap)

    assert not Path(snap["dir"]).exists()
    assert (project / "app.py").read_text() == "faster\n"
    assert list_backups(project) == []


def test_snapshot_rejects_paths_outside_root(project):
    with pytest.raises(ValueError):
        snapshot(project, ["../outside.py"])
    with pytest.raises(ValueError):
        snapshot(project, [])


def test_snapshot_dedupes_paths(project):
    snap = snapshot(project, ["app.py", "app.py"])
    assert len(snap["files"]) == 1


def test_recover_latest_restores_newest_snapshot(project, monkeypatch):
    ids = iter(["20260101T000000-aaaa", "20260101T000001-bbbb"])
    monkeypatch.setattr(backup, "_new_id", lambda: next(ids))

    first = snapshot(project, ["app.py"])
    (project / "app.py").write_text("v1\n")
    discard(first)  # v1 accepted

    snapshot(project, ["app.py"])  # trial starts, then the process "crashes"
    (project / "app.py").write_text("v2 half-written\n")

    recovered = recover_latest(project)

    assert recovered["id"] == "20260101T000001-bbbb"
    assert (project / "app.py").read_text() == "v1\n"
    assert list_backups(project) == []
    assert recover_latest(project) is None


def test_restore_fails_loudly_if_backup_copy_is_missing(project):
    snap = snapshot(project, ["app.py"])
    (Path(snap["dir"]) / "app.py").unlink()

    with pytest.raises(FileNotFoundError):
        restore(snap)
