"""Verifier: safety net around every candidate change.

Backup/rollback, running the project's tests, diffs, and reporting.
"""

from .apply import ApplyError, apply_candidate, edits_of
from .backup import discard, list_backups, recover_latest, restore, snapshot
from .evaluate import REJECTION_REASONS, evaluate_candidate
from .diff import diff_snapshot, diff_stats, render_diff
from .report import final_report, format_pass, format_report, pass_report
from .select import apply_winner, choose_winner, summarize
from .test_runner import run_tests

__all__ = [
    "REJECTION_REASONS",
    "ApplyError",
    "apply_candidate",
    "apply_winner",
    "choose_winner",
    "edits_of",
    "evaluate_candidate",
    "final_report",
    "format_pass",
    "format_report",
    "diff_snapshot",
    "diff_stats",
    "discard",
    "list_backups",
    "pass_report",
    "recover_latest",
    "render_diff",
    "restore",
    "run_tests",
    "snapshot",
    "summarize",
]
