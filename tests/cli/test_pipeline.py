import io
from pathlib import Path

from optimizer.agent import MockLLMClient
from optimizer.pipeline import (
    EXIT_FAILED,
    EXIT_NOTHING_APPLIED,
    EXIT_OK,
    NO_HOTSPOT_MESSAGE,
    NO_TESTS_WARNING,
    RunConfig,
    build_hotspot,
    inspect,
    resolve_hotspot,
    run,
    workload_file,
)
from optimizer.scanner import ProjectScanner
from optimizer.term import Console
from optimizer.verifier import list_backups

from .conftest import (
    LIB,
    TESTS_FAIL,
    TESTS_PASS,
    WORKLOAD,
    StubClient,
    candidate,
    fake_measure,
    fake_profiler,
)

FASTER = LIB.replace("range(3000)", "range(1)")
BROKEN = LIB.replace("return total", "return -1")


def console() -> Console:
    return Console(stream=io.StringIO(), color=False)


def cfg(project: Path, **kw) -> RunConfig:
    base = {"path": str(project), "workload": WORKLOAD, "test": TESTS_PASS, "yes": True, "profile_fn": None}
    base.update(kw)
    return RunConfig(**base)


# --------------------------------------------------------------------------- #
# hotspots
# --------------------------------------------------------------------------- #


def test_workload_file_extraction():
    assert workload_file("python scripts/perf.py --n 3") == "scripts/perf.py"
    assert workload_file("python ./bench.py") == "bench.py"
    assert workload_file("pytest -q") is None
    assert workload_file(None) is None


def test_build_hotspot_manual_and_leaf(project):
    scanner = ProjectScanner(str(project)).scan()
    h = build_hotspot(scanner, scanner.find_function("summarize"))
    assert h["function"] == "summarize" and h["file"] == "lib.py" and h["source"] == "manual"
    assert h["runtime_percent"] is None and h["calls"] is None
    assert h["dependencies"] == ["lib.parse"]
    assert h["related_files"][0] == "lib.py"

    leaf = build_hotspot(scanner, scanner.find_function("parse"), {"calls": 600, "runtime_percent": 91.0})
    assert leaf["dependencies"] == []  # bare names like `range`/`ord` are dropped
    assert leaf["calls"] == 600 and leaf["source"] == "profiler"


def test_resolve_hotspot_prefers_manual_then_profiler(project):
    scanner = ProjectScanner(str(project)).scan()
    prof = fake_profiler(
        {"function": "main", "file": str(project / "bench.py"), "line": 3, "calls": 1},
        {"function": "nope", "file": "/usr/lib/python3/os.py", "line": 1, "calls": 1},
        {"function": "summarize", "file": str(project / "lib.py"), "line": 12, "calls": 60, "runtime_percent": 99.0},
        {"function": "parse", "file": "lib.py", "line": 5, "calls": 600},
    )
    config = cfg(project, hotspots=("parse",), profile_fn=prof)
    first = resolve_hotspot(scanner, config, project, 1, set())
    assert first["function"] == "parse" and first["source"] == "manual"
    assert prof.calls == []

    second = resolve_hotspot(scanner, config, project, 2, {"lib.parse"})
    assert second["function"] == "summarize" and second["calls"] == 60  # bench.py and stdlib skipped
    third = resolve_hotspot(scanner, config, project, 2, {"lib.parse", "lib.summarize"})
    assert third is None


def test_unknown_manual_hotspot_fails_before_any_llm_call(project):
    client = StubClient([candidate("candidate_a", FASTER)])
    out = console()
    res = run(cfg(project, hotspots=("nothing_here",), client=client), out, lambda: True)
    assert res.exit_code == EXIT_FAILED
    assert "Unknown function 'nothing_here'" in out.stream.getvalue()
    assert client.calls == 0


def test_manual_list_exhausted_stops_with_hint(project):
    client = StubClient([candidate("candidate_a", LIB)])  # identical -> no_change
    out = console()
    res = run(cfg(project, hotspots=("parse",), passes=3, client=client, measure_fn=fake_measure(500.0)), out, lambda: True)
    assert res.exit_code == EXIT_NOTHING_APPLIED
    assert len(res.passes) == 1
    assert NO_HOTSPOT_MESSAGE in out.stream.getvalue()


# --------------------------------------------------------------------------- #
# setup failures
# --------------------------------------------------------------------------- #


def test_workload_failing_at_baseline(project):
    client = StubClient([candidate("candidate_a", FASTER)])
    out = console()
    res = run(cfg(project, workload=f"{WORKLOAD} --boom", hotspots=("parse",), client=client,
                  measure_fn=fake_measure(0.0, exit_code=2)), out, lambda: True)
    assert res.exit_code == EXIT_FAILED
    assert "Workload failed at baseline" in out.stream.getvalue()
    assert client.calls == 0


def test_tests_failing_at_baseline(project):
    out = console()
    res = run(cfg(project, test=TESTS_FAIL, hotspots=("parse",), client=StubClient([])), out, lambda: True)
    assert res.exit_code == EXIT_FAILED
    assert "Tests fail before any change" in out.stream.getvalue()


def test_missing_path():
    out = console()
    res = run(cfg(Path("/definitely/not/here"), hotspots=("x",)), out, lambda: True)
    assert res.exit_code == EXIT_FAILED
    assert "Not a directory" in out.stream.getvalue()


def test_no_test_command_warns_and_proceeds(project):
    client = StubClient([candidate("candidate_a", FASTER)])
    out = console()
    res = run(cfg(project, test=None, hotspots=("parse",), client=client, measure_fn=fake_measure(500.0, 100.0)),
              out, lambda: True)
    assert NO_TESTS_WARNING in out.stream.getvalue()
    assert res.exit_code == EXIT_OK
    assert res.report["tests"] is None


# --------------------------------------------------------------------------- #
# the loop
# --------------------------------------------------------------------------- #


def test_all_candidates_rejected_leaves_project_untouched(project):
    client = StubClient([
        candidate("candidate_a", BROKEN, strategy="breaks tests"),
        candidate("candidate_b", LIB.replace("31", "37"), strategy="slower"),
    ])
    out = console()
    res = run(cfg(project, hotspots=("parse",), client=client, measure_fn=fake_measure(500.0, 900.0)), out, lambda: True)
    assert res.exit_code == EXIT_NOTHING_APPLIED
    assert (project / "lib.py").read_text() == LIB
    assert list_backups(project) == []
    text = out.stream.getvalue()
    assert "Result: REJECTED (failed tests)" in text
    assert "Result: REJECTED (produced slower benchmarks)" in text
    assert "No valid candidate. Nothing applied." in text
    assert res.report["attempted"] == 2 and res.report["accepted"] == 0


def test_winner_applied_with_yes(project):
    client = StubClient([
        candidate("candidate_a", FASTER, strategy="fewer iterations"),
        candidate("candidate_b", LIB.replace("31", "37"), strategy="meh"),
    ])
    timing = fake_measure(800.0, 200.0, 700.0)  # baseline, candidate_a, candidate_b
    out = console()
    res = run(cfg(project, hotspots=("parse",), client=client, measure_fn=timing), out, lambda: True)
    assert res.exit_code == EXIT_OK and res.applied_any
    assert (project / "lib.py").read_text() == FASTER
    assert res.report["final_ms"] == 200.0 and round(res.report["speedup"], 1) == 4.0
    assert res.passes[0]["winner"]["candidate_id"] == "candidate_a"
    text = out.stream.getvalue()
    assert "Selected Candidate A" in text and "Speedup: 4.0x" in text
    assert "+" in text and "range(1)" in text  # diff shown
    assert "Applied candidate_a." in text
    assert text.count("Tests: ") >= 2  # baseline and final test runs
    assert timing.calls[0] == project  # baseline measured in the project root


def test_declined_confirmation_keeps_original(project):
    client = StubClient([candidate("candidate_a", FASTER)])
    out = console()
    res = run(cfg(project, yes=False, hotspots=("parse",), client=client, measure_fn=fake_measure(800.0, 200.0)),
              out, lambda: False)
    assert res.exit_code == EXIT_OK and res.declined and not res.applied_any
    assert (project / "lib.py").read_text() == LIB
    assert res.passes[0]["applied"] is False
    assert "Not applied." in out.stream.getvalue()


def test_two_passes_rebaseline(project):
    client = StubClient([candidate("candidate_a", FASTER)], [candidate("candidate_a", FASTER.replace("31", "37"))])
    # baseline 800, pass-1 candidate 300, re-measure 310, pass-2 candidate 100
    timing = fake_measure(800.0, 300.0, 310.0, 100.0)
    out = console()
    res = run(cfg(project, hotspots=("parse", "summarize"), passes=2, client=client, measure_fn=timing), out, lambda: True)
    assert res.exit_code == EXIT_OK
    assert [p["pass_number"] for p in res.passes] == [1, 2]
    assert res.passes[1]["baseline_ms"] == 310.0
    assert res.report["baseline_ms"] == 800.0 and res.report["final_ms"] == 100.0
    assert res.report["accepted"] == 2
    assert "PASS 1" in out.stream.getvalue() and "Re-profiling..." in out.stream.getvalue()


def test_end_to_end_with_mock_agent_and_real_timing(project):
    """The offline demo path: MockLLMClient wraps `parse` in lru_cache and wins for real."""
    out = console()
    res = run(cfg(project, hotspots=("parse",), client=MockLLMClient()), out, lambda: True)
    text = out.stream.getvalue()
    assert res.exit_code == EXIT_OK, text
    assert "Candidate A" in text and "REJECTED (no change)" in text
    assert "Candidate B" in text and "Result: VALID" in text
    assert "@functools.lru_cache" in (project / "lib.py").read_text()
    assert res.report["speedup"] > 1.05


def test_result_json_roundtrip(project):
    import json

    res = run(cfg(project, hotspots=("parse",), client=StubClient([candidate("a", FASTER)]),
                  measure_fn=fake_measure(800.0, 200.0)), console(), lambda: True)
    payload = json.loads(json.dumps(res.to_json()))
    assert payload["exit_code"] == 0 and payload["report"]["speedup"] == 4.0
    assert payload["passes"][0]["hotspot"]["function"] == "parse"


# --------------------------------------------------------------------------- #
# inspect
# --------------------------------------------------------------------------- #


def test_inspect_static_view(project):
    out = console()
    info = inspect(cfg(project, hotspots=()), out)
    text = out.stream.getvalue()
    assert info["exit_code"] == EXIT_OK
    assert "1 Python files found" in text and "2 functions indexed" in text
    assert "Profiling execution" not in text
    assert "static view" in text
    assert info["hotspots"][0]["function"] == "summarize"  # ranked by resolved dependencies
    assert "Affected files:\n- lib.py" in text
    assert info["files"] == 1 and info["loc"] > 0


def test_inspect_with_profiler_and_named(project):
    prof = fake_profiler({"function": "parse", "file": "lib.py", "line": 5, "calls": 600, "runtime_percent": 91.0})
    info = inspect(cfg(project, hotspots=(), profile_fn=prof), console())
    assert prof.calls == [WORKLOAD]
    assert [h["function"] for h in info["hotspots"]] == ["parse"]
    assert info["hotspots"][0]["runtime_percent"] == 91.0

    info = inspect(cfg(project, hotspots=("summarize",)), console())
    assert [h["function"] for h in info["hotspots"]] == ["summarize"]

    out = console()
    assert inspect(cfg(project, hotspots=("ghost",)), out)["exit_code"] == EXIT_FAILED
    assert "Unknown function 'ghost'" in out.stream.getvalue()
