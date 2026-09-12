from optimizer.verifier.report import (
    final_report,
    format_candidate,
    format_pass,
    format_report,
    pass_report,
)

HOTSPOT = {
    "function": "generate_feed",
    "qualified_name": "services.recommendations.generate_feed",
    "file": "services/recommendations.py",
    "line": 41,
    "calls": 10420,
    "self_time": 0.62,
    "cumulative_time": 1.82,
    "runtime_percent": 62.0,
    "dependencies": ["services.users.get_user", "database.find_user"],
    "related_files": ["services/recommendations.py", "services/users.py", "database.py"],
}


def res(cid, strategy, accepted, after=None, reason=None, tests=(34, 34), files=("services/recommendations.py",)):
    return {
        "candidate_id": cid,
        "strategy": strategy,
        "explanation": "Batches the lookups.",
        "edits": [{"path": f, "new_content": "x\n"} for f in files],
        "accepted": accepted,
        "rejection_reason": reason,
        "tests": {"passed": tests[0] == tests[1], "skipped": False, "total": tests[1],
                  "passed_count": tests[0], "failed": tests[1] - tests[0]}
        if tests else None,
        "benchmark": {"before_ms": 840.0, "after_ms": after, "speedup": 840.0 / after if after else None}
        if after is not None else None,
        "diff": "--- a/services/recommendations.py\n+++ b/services/recommendations.py\n-old\n+new\n",
        "error": None,
    }


A = res("candidate_a", "batch user retrieval", True, 191.0, files=("services/recommendations.py", "services/users.py"))
B = res("candidate_b", "local caching", True, 303.0)
C = res("candidate_c", "concurrent execution", False, reason="tests_failed", tests=(32, 34))


def test_format_candidate_matches_brief():
    assert format_candidate(A) == (
        "Candidate A\nStrategy: batch user retrieval\nRuntime: 191 ms\n"
        "Tests: 34/34 passed\nResult: VALID"
    )
    assert format_candidate(C) == (
        "Candidate C\nStrategy: concurrent execution\nRuntime: n/a\n"
        "Tests: 32/34 passed\nResult: REJECTED (failed tests)"
    )


def test_format_candidate_edge_cases():
    apply_failed = res("candidate_d", "x", False, reason="apply_failed", tests=None)
    apply_failed["error"] = "syntax error in a.py line 3"
    out = format_candidate(apply_failed)
    assert "Tests: not run" in out and "REJECTED (failed to apply)" in out
    assert "syntax error in a.py line 3" in out

    skipped = res("candidate_e", "x", True, 500.0)
    skipped["tests"] = {"passed": True, "skipped": True, "total": None, "passed_count": None, "failed": None}
    assert "Tests: skipped (no test command)" in format_candidate(skipped)

    no_change = res("candidate_f", "x", False, reason="no_change", tests=None)
    assert "REJECTED (no change)" in format_candidate(no_change)


def test_pass_report_numbers():
    pr = pass_report(HOTSPOT, 840.0, [A, B, C], winner=A, applied=True)
    assert pr["after_ms"] == 191.0
    assert round(pr["speedup"], 1) == 4.4
    assert round(pr["reduction_percent"], 1) == 77.3
    assert pr["files_changed"] == ["services/recommendations.py", "services/users.py"]
    assert pr["attempted"] == 3 and pr["accepted"] == 2
    assert pr["rejected"] == {"tests_failed": 1}
    assert pr["winner"]["candidate_id"] == "candidate_a"


def test_pass_report_without_winner():
    pr = pass_report(HOTSPOT, 840.0, [C], winner=None, applied=False)
    assert pr["after_ms"] is None and pr["speedup"] is None
    assert pr["files_changed"] == [] and pr["diff"] == ""
    assert "No valid candidate. Nothing applied." in format_pass(pr)


def test_format_pass_matches_brief_layout():
    pr = pass_report(HOTSPOT, 840.0, [A, B, C], winner=A, applied=True)
    text = format_pass(pr)
    assert text.startswith("Targeting:\nservices/recommendations.py::generate_feed")
    assert "62% of total runtime\n10,420 calls" in text
    assert "services.recommendations.generate_feed\n    ↓\nservices.users.get_user\n    ↓\ndatabase.find_user" in text
    assert "Baseline: 840 ms" in text
    assert "Candidate A" in text and "Candidate B" in text and "Candidate C" in text
    assert "Selected Candidate A\nBefore: 840 ms\nAfter:  191 ms\nSpeedup: 4.4x\nRuntime reduction: 77.3%" in text
    assert "Files changed:\n- services/recommendations.py\n- services/users.py" in text
    assert "+new" in text
    assert "Why this is faster:\nBatches the lookups." in text
    assert "+new" not in format_pass(pr, show_diff=False)


def test_final_report_aggregates_passes():
    p1 = pass_report(HOTSPOT, 3470.0, [A, B, C], winner=A, applied=True, pass_number=1)
    p2 = pass_report(HOTSPOT, 1900.0, [res("candidate_a", "x", False, 2100.0, reason="slower"),
                                       res("candidate_b", "y", False, reason="tests_failed", tests=(1, 2))],
                     winner=None, applied=False, pass_number=2)
    p3 = pass_report(HOTSPOT, 1900.0, [res("candidate_a", "z", True, 910.0, files=("database.py",))],
                     winner=res("candidate_a", "z", True, 910.0, files=("database.py",)), applied=True, pass_number=3)
    fr = final_report(
        {"files": 23, "loc": 4201, "functions": 61}, 3470.0, 910.0, [p1, p2, p3],
        tests={"passed": True, "skipped": False, "total": 42, "passed_count": 42, "failed": 0},
    )
    assert fr["attempted"] == 6
    assert fr["accepted"] == 2
    assert fr["rejected"] == {"tests_failed": 2, "slower": 1}
    assert round(fr["speedup"], 1) == 3.8
    assert round(fr["improvement_percent"]) == 74
    assert fr["files_changed"] == ["services/recommendations.py", "services/users.py", "database.py"]

    text = format_report(fr)
    assert text.startswith("Optimizer Report\n")
    assert "Repository\n23 files\n4,201 LOC\n61 functions analyzed" in text
    assert "Baseline\n3.47 sec" in text
    assert "Optimizations attempted\n6" in text
    assert "Accepted\n2" in text
    assert "Rejected\n3\n- 2 failed tests\n- 1 produced slower benchmarks" in text
    assert "Final runtime\n0.91 sec" in text
    assert "Overall improvement\n74% faster" in text
    assert "Speedup\n3.8x" in text
    assert "Tests\n42/42 passing" in text
    assert "Files changed\n3" in text


def test_final_report_with_nothing_applied():
    p = pass_report(HOTSPOT, 1000.0, [C], winner=None, applied=False)
    fr = final_report(None, 1000.0, 1000.0, [p])
    assert fr["accepted"] == 0 and fr["files_changed"] == []
    assert round(fr["improvement_percent"]) == 0
    text = format_report(fr)
    assert "Repository" not in text
    assert "Overall improvement\n0% faster" in text
