"""Verifier: safety net around every candidate change.

Backup/rollback, running the project's tests, diffs, and reporting.
"""

from .apply import ApplyError, apply_candidate, edits_of
from .backup import discard, list_backups, recover_latest, restore, snapshot
from .diff import diff_snapshot, diff_stats, render_diff
from .evaluate import REJECTION_REASONS, evaluate_candidate
from .report import (
    final_report,
    format_candidate,
    format_hotspot,
    format_pass,
    format_report,
    format_winner,
    pass_report,
)
from .select import apply_winner, choose_winner, summarize
from .test_runner import run_tests

__all__ = [
    "REJECTION_REASONS",
    "ApplyError",
    "apply_candidate",
    "apply_winner",
    "choose_winner",
    "diff_snapshot",
    "diff_stats",
    "discard",
    "edits_of",
    "evaluate_candidate",
    "final_report",
    "format_candidate",
    "format_hotspot",
    "format_pass",
    "format_report",
    "format_winner",
    "list_backups",
    "pass_report",
    "recover_latest",
    "render_diff",
    "restore",
    "run_tests",
    "snapshot",
    "summarize",
]
