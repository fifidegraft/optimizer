"""Pick the winner among evaluated candidates and apply it for real.

    results = [evaluate_candidate(root, c, ...) for c in candidates]
    winner = choose_winner(results)          # fastest accepted result, or None
    if winner:
        applied = apply_winner(root, winner)  # files written, backup discarded

Both work on the dicts evaluate_candidate() returns.
"""

from __future__ import annotations

from pathlib import Path

from .apply import apply_candidate
from .backup import discard
from .diff import diff_snapshot


def choose_winner(results: list[dict]) -> dict | None:
    """The accepted result with the lowest after_ms. Ties keep the earlier candidate."""
    best = None
    for r in results:
        if not r.get("accepted"):
            continue
        after = (r.get("benchmark") or {}).get("after_ms")
        if after is None:
            continue
        if best is None or after < best["benchmark"]["after_ms"]:
            best = r
    return best


def apply_winner(root: str | Path, winner: dict) -> dict:
    """Write the winning candidate permanently and drop its backup.

    Returns {"candidate_id", "files_changed", "diff"}. Raises ApplyError if the
    files cannot be written; in that case the project is left unchanged.
    """
    snap = apply_candidate(root, winner)
    diff = diff_snapshot(snap)
    discard(snap)
    return {
        "candidate_id": winner.get("candidate_id"),
        "files_changed": [f["path"] for f in snap["files"]],
        "diff": diff,
    }


def summarize(results: list[dict], winner: dict | None) -> dict:
    """Counts for reporting: attempted, accepted, rejected by reason."""
    rejected: dict[str, int] = {}
    accepted = 0
    for r in results:
        if r.get("accepted"):
            accepted += 1
        elif r.get("rejection_reason"):
            rejected[r["rejection_reason"]] = rejected.get(r["rejection_reason"], 0) + 1
    return {
        "attempted": len(results),
        "accepted": accepted,
        "rejected": rejected,
        "winner": winner.get("candidate_id") if winner else None,
    }
