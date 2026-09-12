"""Apply a candidate's edits to the project, with a snapshot for rollback.

Candidate shape (agreed with the agent module):
    {"candidate_id": "candidate_a", "strategy": "...", "explanation": "...",
     "edits": [{"path": "services/users.py", "new_content": "<complete file>"}, ...]}

    snap = apply_candidate(root, candidate)   # files on disk now hold the candidate
    ...tests, benchmark...
    restore(snap) or discard(snap)

apply_candidate() is all-or-nothing: if any edit cannot be written, every
file is restored and ApplyError is raised. Python files are syntax-checked
before anything is written, so an unparseable candidate never touches disk.
"""

from __future__ import annotations

from pathlib import Path

from .backup import restore, snapshot

MAX_EDITS = 3


class ApplyError(Exception):
    """The candidate could not be applied. The project is unchanged."""


def edits_of(candidate: dict) -> list[tuple[str, str]]:
    """Read (path, new_content) pairs out of a candidate. The only place that knows the schema."""
    if not isinstance(candidate, dict):
        raise ApplyError("candidate must be a dict")
    edits = candidate.get("edits")
    if not isinstance(edits, list) or not edits:
        raise ApplyError("candidate has no edits")
    if len(edits) > MAX_EDITS:
        raise ApplyError(f"candidate touches {len(edits)} files (max {MAX_EDITS})")

    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for i, edit in enumerate(edits):
        if not isinstance(edit, dict):
            raise ApplyError(f"edit {i} is not a dict")
        path = edit.get("path")
        content = edit.get("new_content")
        if not isinstance(path, str) or not path.strip():
            raise ApplyError(f"edit {i} has no path")
        if not isinstance(content, str):
            raise ApplyError(f"edit {i} ({path}) has no new_content")
        path = Path(path).as_posix()
        if Path(path).is_absolute():
            raise ApplyError(f"edit {i} path must be relative: {path}")
        if path in seen:
            raise ApplyError(f"duplicate edit for {path}")
        seen.add(path)
        pairs.append((path, content))
    return pairs


def check_syntax(path: str, content: str) -> None:
    """Raise ApplyError if a .py file would not even compile."""
    if not path.endswith(".py"):
        return
    try:
        compile(content, path, "exec")
    except SyntaxError as exc:
        raise ApplyError(f"syntax error in {path} line {exc.lineno}: {exc.msg}") from exc


def apply_candidate(root: str | Path, candidate: dict) -> dict:
    """Write the candidate's files. Returns the snapshot to restore() or discard() later."""
    root = Path(root).resolve()
    pairs = edits_of(candidate)
    for path, content in pairs:
        check_syntax(path, content)

    try:
        snap = snapshot(root, [p for p, _ in pairs])
    except ValueError as exc:  # path outside root
        raise ApplyError(str(exc)) from exc

    try:
        for path, content in pairs:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
    except OSError as exc:
        restore(snap)
        raise ApplyError(f"could not write {path}: {exc}") from exc
    return snap
