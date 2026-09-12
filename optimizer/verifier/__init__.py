"""Verifier: safety net around every candidate change.

Backup/rollback, running the project's tests, diffs, and reporting.
"""

from .backup import discard, list_backups, recover_latest, restore, snapshot
from .diff import diff_snapshot, diff_stats, render_diff
from .test_runner import run_tests

__all__ = [
    "diff_snapshot",
    "diff_stats",
    "discard",
    "list_backups",
    "recover_latest",
    "render_diff",
    "restore",
    "run_tests",
    "snapshot",
]
