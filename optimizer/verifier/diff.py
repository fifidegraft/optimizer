"""Git-style unified diffs for showing what a candidate changed.

Two entry points, neither depends on the candidate schema:

    render_diff("services/users.py", before_text, after_text)  # one file
    diff_snapshot(snap)   # every file in a backup snapshot vs. what is on disk now

The second is the one the pipeline uses: after applying a candidate, the
snapshot holds the originals and the disk holds the candidate, so the diff
falls out with no knowledge of how the candidate was expressed.
"""

from __future__ import annotations

import difflib
from pathlib import Path


def render_diff(path: str, before: str, after: str) -> str:
    """Unified diff with git-style a/ b/ headers. Empty string if nothing changed."""
    if before == after:
        return ""
    lines = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{path}" if before else "/dev/null",
        tofile=f"b/{path}" if after else "/dev/null",
    )
    text = "".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def diff_snapshot(snap: dict) -> str:
    """Diff every snapshotted file: backup copy (before) vs. current disk (after)."""
    root = Path(snap["root"])
    backup_dir = Path(snap["dir"])
    chunks = []
    for entry in snap["files"]:
        rel = entry["path"]
        before = _read(backup_dir / rel) if entry["existed"] else ""
        current = root / rel
        after = _read(current) if current.is_file() else ""
        chunk = render_diff(rel, before, after)
        if chunk:
            chunks.append(chunk)
    return "".join(chunks)


def _read(path: Path) -> str:
    """Read for diffing: utf-8, never crash on odd bytes, keep line endings as-is."""
    return path.read_bytes().decode("utf-8", errors="replace")


def diff_stats(diff_text: str) -> dict:
    """Count files, added and removed lines in a unified diff."""
    files = added = removed = 0
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            files += 1
        elif line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return {"files": files, "added": added, "removed": removed}
