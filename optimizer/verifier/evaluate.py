"""Evaluate one candidate: apply -> tests -> benchmark -> restore.

    result = evaluate_candidate(
        root, candidate,
        test_command="pytest -q",
        benchmark=run_workload,      # callable(cwd) -> {"runtime_ms": float, "exit_code": int, ...}
        baseline_ms=840.0,
    )

The project is always restored afterwards, accepted or not. Applying the
winner for real is a separate step (see select.py) once every candidate has
been measured.

The result is the candidate dict plus:
    "accepted":         bool
    "rejection_reason": None | "apply_failed" | "no_change" | "tests_failed"
                        | "benchmark_failed" | "slower"
    "tests":            run_tests() output, or None if never reached
    "benchmark":        {"before_ms", "after_ms", "speedup", "exit_code", "output"}, or None
    "diff":             unified diff of what the candidate changed ("" if apply failed)
    "error":            message for apply_failed, else None
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .apply import ApplyError, apply_candidate
from .backup import discard, restore
from .diff import diff_snapshot
from .test_runner import run_tests

REJECTION_REASONS = ("apply_failed", "no_change", "tests_failed", "benchmark_failed", "slower")

# A candidate must beat the baseline by at least this fraction to count as faster.
# Single-run timings jitter by a few percent, so 2% is not enough to separate a
# real win from noise; the demo's planted bottlenecks give 2x or better anyway.
DEFAULT_MIN_IMPROVEMENT = 0.05


def evaluate_candidate(
    root: str | Path,
    candidate: dict,
    *,
    test_command: str | None,
    benchmark: Callable[[Path], dict],
    baseline_ms: float,
    min_improvement: float = DEFAULT_MIN_IMPROVEMENT,
    test_timeout: float = 600,
) -> dict:
    root = Path(root).resolve()
    result = {
        **candidate,
        "accepted": False,
        "rejection_reason": None,
        "tests": None,
        "benchmark": None,
        "diff": "",
        "error": None,
    }

    try:
        snap = apply_candidate(root, candidate)
    except ApplyError as exc:
        result["rejection_reason"] = "apply_failed"
        result["error"] = str(exc)
        return result

    try:
        result["diff"] = diff_snapshot(snap)
        if not result["diff"]:
            # Identical to the original: nothing to measure, and timing noise
            # could otherwise "accept" it.
            result["rejection_reason"] = "no_change"
            return result

        tests = run_tests(test_command, root, timeout=test_timeout)
        result["tests"] = tests
        if not tests["passed"]:
            result["rejection_reason"] = "tests_failed"
            return result

        raw = benchmark(root)
        bench = _benchmark_summary(raw, baseline_ms)
        result["benchmark"] = bench
        if bench["exit_code"] != 0:
            result["rejection_reason"] = "benchmark_failed"
            return result

        if bench["after_ms"] > baseline_ms * (1 - min_improvement):
            result["rejection_reason"] = "slower"
            return result

        result["accepted"] = True
        return result
    finally:
        # Originals back, then drop the backup. If restore raises, the backup
        # stays on disk for recover_latest().
        restore(snap)
        discard(snap)


def _benchmark_summary(raw: dict, baseline_ms: float) -> dict:
    """Normalize the profiler's timing dict into the agreed benchmark shape."""
    exit_code = int(raw.get("exit_code", 0))
    raw_ms = raw.get("runtime_ms")
    after_ms = None if exit_code != 0 or raw_ms is None else float(raw_ms)
    speedup = baseline_ms / after_ms if after_ms else None
    return {
        "before_ms": float(baseline_ms),
        "after_ms": after_ms,
        "speedup": speedup,
        "exit_code": exit_code,
        "output": raw.get("output", ""),
    }
