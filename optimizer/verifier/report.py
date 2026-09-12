"""Before/after reporting. Structured dicts plus plain-text rendering.

    pr = pass_report(hotspot, baseline_ms, results, winner, applied)
    print(format_pass(pr))

    fr = final_report(project, baseline_ms, final_ms, passes, tests)
    print(format_report(fr))

The text output follows the brief (§5 candidate blocks, §20 final report). No
color here; the CLI layer can decorate it.
"""

from __future__ import annotations

from .select import summarize

REASON_LABELS = {
    "apply_failed": "failed to apply",
    "no_change": "no change",
    "tests_failed": "failed tests",
    "benchmark_failed": "benchmark crashed",
    "slower": "produced slower benchmarks",
}


# --------------------------------------------------------------------------- #
# structured
# --------------------------------------------------------------------------- #


def pass_report(
    hotspot: dict | None,
    baseline_ms: float,
    results: list[dict],
    winner: dict | None,
    applied: bool,
    pass_number: int = 1,
) -> dict:
    """One PROFILE -> OPTIMIZE -> VERIFY iteration, ready for display or JSON."""
    after_ms = (winner.get("benchmark") or {}).get("after_ms") if winner else None
    counts = summarize(results, winner)
    return {
        "pass_number": pass_number,
        "hotspot": hotspot,
        "baseline_ms": float(baseline_ms),
        "after_ms": after_ms,
        "speedup": _speedup(baseline_ms, after_ms),
        "reduction_percent": _reduction(baseline_ms, after_ms),
        "results": results,
        "winner": winner,
        "applied": applied,
        "files_changed": [e["path"] for e in winner["edits"]] if winner else [],
        "diff": (winner or {}).get("diff", ""),
        "attempted": counts["attempted"],
        "accepted": counts["accepted"],
        "rejected": counts["rejected"],
    }


def final_report(
    project: dict | None,
    baseline_ms: float,
    final_ms: float,
    passes: list[dict],
    tests: dict | None = None,
) -> dict:
    """Whole-run summary (brief §20). `project` may carry files/loc/functions counts."""
    project = project or {}
    rejected: dict[str, int] = {}
    attempted = accepted = 0
    files_changed: list[str] = []
    for p in passes:
        attempted += p["attempted"]
        accepted += 1 if p["applied"] else 0
        for reason, n in p["rejected"].items():
            rejected[reason] = rejected.get(reason, 0) + n
        for f in p["files_changed"]:
            if p["applied"] and f not in files_changed:
                files_changed.append(f)
    return {
        "files": project.get("files"),
        "loc": project.get("loc"),
        "functions": project.get("functions"),
        "baseline_ms": float(baseline_ms),
        "final_ms": float(final_ms),
        "speedup": _speedup(baseline_ms, final_ms),
        "improvement_percent": _reduction(baseline_ms, final_ms),
        "attempted": attempted,
        "accepted": accepted,
        "rejected": rejected,
        "passes": len(passes),
        "files_changed": files_changed,
        "tests": tests,
    }


# --------------------------------------------------------------------------- #
# text
# --------------------------------------------------------------------------- #


def format_candidate(result: dict) -> str:
    """Brief §5 block: Candidate A / Strategy / Runtime / Tests / Result."""
    cid = result.get("candidate_id", "candidate")
    title = cid.replace("_", " ").title()
    lines = [title, f"Strategy: {result.get('strategy', '')}"]

    bench = result.get("benchmark") or {}
    after = bench.get("after_ms")
    lines.append(f"Runtime: {_ms(after)}" if after is not None else "Runtime: n/a")

    tests = result.get("tests")
    if tests is None:
        lines.append("Tests: not run")
    elif tests.get("skipped"):
        lines.append("Tests: skipped (no test command)")
    elif tests.get("total") is not None:
        lines.append(f"Tests: {tests['passed_count']}/{tests['total']} passed")
    else:
        lines.append("Tests: passed" if tests.get("passed") else "Tests: failed")

    if result.get("accepted"):
        lines.append("Result: VALID")
    else:
        reason = REASON_LABELS.get(result.get("rejection_reason"), result.get("rejection_reason"))
        lines.append(f"Result: REJECTED ({reason})" if reason else "Result: REJECTED")
        if result.get("error"):
            lines.append(f"  {result['error']}")
    return "\n".join(lines)


def format_hotspot(hotspot: dict) -> str:
    """Brief §5 'Targeting' block."""
    lines = [f"Targeting:\n{hotspot.get('file', '?')}::{hotspot.get('function', '?')}"]
    if hotspot.get("runtime_percent") is not None:
        lines.append(f"{hotspot['runtime_percent']:.0f}% of total runtime")
    if hotspot.get("calls") is not None:
        lines.append(f"{hotspot['calls']:,} calls")
    deps = hotspot.get("dependencies") or []
    if deps:
        chain = [hotspot.get("qualified_name", hotspot.get("function", "?")), *deps]
        lines.append("\nRelated execution path:\n" + "\n    ↓\n".join(chain))
    return "\n".join(lines)


def format_pass(pr: dict, show_diff: bool = True) -> str:
    parts = []
    if pr.get("hotspot"):
        parts.append(format_hotspot(pr["hotspot"]))
    parts.append(f"Baseline: {_ms(pr['baseline_ms'])}")
    for r in pr["results"]:
        parts.append(format_candidate(r))

    parts.append(format_winner(pr, show_diff=show_diff))
    return "\n\n".join(parts)


def format_winner(pr: dict, show_diff: bool = True) -> str:
    """Brief §5 tail: Selected / Before / After / Speedup / Files changed, then the diff."""
    w = pr.get("winner")
    if w is None:
        return "No valid candidate. Nothing applied."
    title = w["candidate_id"].replace("_", " ").title()
    block = [
        f"Selected {title}",
        f"Before: {_ms(pr['baseline_ms'])}",
        f"After:  {_ms(pr['after_ms'])}",
        f"Speedup: {pr['speedup']:.1f}x",
        f"Runtime reduction: {pr['reduction_percent']:.1f}%",
        "Files changed:\n" + "\n".join(f"- {f}" for f in pr["files_changed"]),
    ]
    if not pr["applied"]:
        block.append("(not applied)")
    parts = ["\n".join(block)]
    if show_diff and pr.get("diff"):
        parts.append(pr["diff"].rstrip("\n"))
        if w.get("explanation"):
            parts.append(f"Why this is faster:\n{w['explanation']}")
    return "\n\n".join(parts)


def format_report(fr: dict) -> str:
    """Brief §20 final report."""
    rule = "─" * 32
    rows: list[tuple[str, str]] = []

    repo = []
    if fr.get("files") is not None:
        repo.append(f"{fr['files']} files")
    if fr.get("loc") is not None:
        repo.append(f"{fr['loc']:,} LOC")
    if fr.get("functions") is not None:
        repo.append(f"{fr['functions']} functions analyzed")
    if repo:
        rows.append(("Repository", "\n".join(repo)))

    rows.append(("Baseline", _sec(fr["baseline_ms"])))
    rows.append(("Optimizations attempted", str(fr["attempted"])))
    rows.append(("Accepted", str(fr["accepted"])))
    rejected_n = sum(fr["rejected"].values())
    rej_lines = [str(rejected_n)] + [
        f"- {n} {REASON_LABELS.get(reason, reason)}" for reason, n in fr["rejected"].items()
    ]
    rows.append(("Rejected", "\n".join(rej_lines)))
    rows.append(("Final runtime", _sec(fr["final_ms"])))
    if fr["improvement_percent"] is not None:
        rows.append(("Overall improvement", f"{fr['improvement_percent']:.0f}% faster"))
        rows.append(("Speedup", f"{fr['speedup']:.1f}x"))
    tests = fr.get("tests")
    if tests and tests.get("total") is not None:
        rows.append(("Tests", f"{tests['passed_count']}/{tests['total']} passing"))
    elif tests and not tests.get("skipped"):
        rows.append(("Tests", "passing" if tests.get("passed") else "FAILING"))
    rows.append(("Files changed", str(len(fr["files_changed"]))))

    body = "\n\n".join(f"{label}\n{value}" for label, value in rows)
    return f"Optimizer Report\n{rule}\n\n{body}"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _speedup(before: float, after: float | None) -> float | None:
    return before / after if after else None


def _reduction(before: float, after: float | None) -> float | None:
    return (1 - after / before) * 100 if after is not None and before else None


def _ms(ms: float | None) -> str:
    if ms is None:
        return "n/a"
    return f"{ms / 1000:.2f} sec" if ms >= 1000 else f"{ms:.0f} ms"


def _sec(ms: float) -> str:
    return f"{ms / 1000:.2f} sec"
