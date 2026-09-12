"""Backup and rollback for candidate trials.

Every candidate goes: snapshot -> apply -> tests/benchmark -> restore (or discard).
Backups live on disk under <root>/.optimizer/backups/<id>/ so a crash mid-trial
is recoverable with recover_latest().

    snap = snapshot(root, ["services/users.py", "services/recommendations.py"])
    ...write candidate files...
    restore(snap)    # candidate rejected: originals back, new files removed
    discard(snap)    # candidate accepted: drop the backup

A snapshot is a plain dict:
    {"id": "20260912T141503-3f9a", "root": "/abs/project", "dir": "/abs/project/.optimizer/backups/<id>",
     "files": [{"path": "services/users.py", "existed": True, "sha256": "..."}, ...]}
"""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path

BACKUP_ROOT = Path(".optimizer") / "backups"
MANIFEST = "manifest.json"


def _resolve_inside(root: Path, rel_path: str) -> Path:
    """Return root/rel_path, refusing anything that escapes root."""
    target = (root / rel_path).resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"{rel_path!r} is outside the project root")
    return target


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _new_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{secrets.token_hex(2)}"


def snapshot(root: str | Path, paths: list[str]) -> dict:
    """Copy each file in `paths` (relative to root) into a new backup directory.

    Files that do not exist yet are recorded with existed=False so restore()
    can delete them if the candidate creates them.
    """
    root = Path(root).resolve()
    if not paths:
        raise ValueError("snapshot needs at least one path")

    # Validate every path before creating anything, so a bad path leaves no half-made backup.
    resolved: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for rel in paths:
        rel = Path(rel).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        resolved.append((rel, _resolve_inside(root, rel)))

    snap_id = _new_id()
    backup_dir = root / BACKUP_ROOT / snap_id
    backup_dir.mkdir(parents=True, exist_ok=False)

    files = []
    for rel, src in resolved:
        entry = {"path": rel, "existed": src.is_file(), "sha256": None}
        if entry["existed"]:
            dst = backup_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            entry["sha256"] = _sha256(src)
        files.append(entry)

    snap = {"id": snap_id, "root": str(root), "dir": str(backup_dir), "files": files}
    (backup_dir / MANIFEST).write_text(json.dumps(snap, indent=2))
    return snap


def restore(snap: dict) -> list[str]:
    """Put every snapshotted file back. Returns the relative paths touched.

    Files that existed are overwritten with the backup copy; files that did not
    exist are deleted if the candidate created them. Safe to call twice.
    """
    root = Path(snap["root"])
    backup_dir = Path(snap["dir"])
    touched = []
    for entry in snap["files"]:
        target = _resolve_inside(root, entry["path"])
        if entry["existed"]:
            src = backup_dir / entry["path"]
            if not src.is_file():
                raise FileNotFoundError(f"backup copy missing: {src}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            if _sha256(target) != entry["sha256"]:
                raise RuntimeError(f"restore verification failed for {entry['path']}")
        elif target.exists():
            target.unlink()
        touched.append(entry["path"])
    return touched


def discard(snap: dict) -> None:
    """Accept the current state of the files and delete the backup."""
    backup_dir = Path(snap["dir"])
    if backup_dir.is_dir():
        shutil.rmtree(backup_dir)


def list_backups(root: str | Path) -> list[dict]:
    """All on-disk snapshots for a project, newest first."""
    base = Path(root).resolve() / BACKUP_ROOT
    if not base.is_dir():
        return []
    snaps = []
    for d in base.iterdir():
        manifest = d / MANIFEST
        if manifest.is_file():
            snaps.append(json.loads(manifest.read_text()))
    snaps.sort(key=lambda s: s["id"], reverse=True)
    return snaps


def recover_latest(root: str | Path) -> dict | None:
    """After a crash: restore the newest snapshot and remove it. None if there is none."""
    snaps = list_backups(root)
    if not snaps:
        return None
    snap = snaps[0]
    restore(snap)
    discard(snap)
    return snap
