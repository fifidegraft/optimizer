"""Verifier: safety net around every candidate change.

Backup/rollback, running the project's tests, diffs, and reporting.
"""

from .backup import discard, list_backups, recover_latest, restore, snapshot

__all__ = ["discard", "list_backups", "recover_latest", "restore", "snapshot"]
