"""The loop: scan -> baseline -> hotspot -> candidates -> evaluate -> apply -> repeat.

    result = run(RunConfig(path="demo", workload="python scripts/performance_scenario.py",
                           test="pytest -q", hotspots=["parse_record"]), console, confirm)

Everything the loop depends on is injectable (LLM client, timing function,
profiler hook, confirmation prompt) so it can be tested without argv, network
or real timing. `cli.py` is the only caller that wires it to the terminal.

Hotspot identification: the profiler owner exposes `profile_workload` (see
PROFILER_CONTRACT). Until it lands, `--hotspot NAME` names the target.
"""

from __future__ import annotations

import shlex
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from optimizer.agent import generate_candidates, get_llm_client
from optimizer.profiler import benchmark_workload
from optimizer.scanner import ProjectScanner
from optimizer.term import Console
from optimizer.verifier import (
    apply_winner,
    choose_winner,
    evaluate_candidate,
    final_report,
    format_candidate,
    format_hotspot,
    format_winner,
    pass_report,
    run_tests,
)

PROFILER_CONTRACT = """\
def profile_workload(command: str, cwd: str = ".", timeout: int = 300, limit: int = 20) -> dict:
    Run `command` under cProfile and rank the hottest project functions.
    Returns {"exit_code": int, "output": str, "hotspots": [ranked, best first]} where each
    hotspot is {"function", "file" (as pstats reports it), "line", "calls", "self_time",
    "cumulative_time", "runtime_percent"}. Never raises; exit_code -1 on failure. Excludes
    stdlib and site-packages frames. Rank by score or self_time, not pure cumulative time.
"""

NO_TESTS_WARNING = """\
WARNING:
No test command provided.

Optimizer can measure performance,
but cannot automatically verify behavior."""

NO_HOTSPOT_MESSAGE = (
    "No additional high-impact optimization found.\n"
    "(The profiler does not rank hotspots yet; pass --hotspot NAME to choose a target.)"
)

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_NOTHING_APPLIED = 3


class PipelineError(Exception):
    """A setup problem the user has to fix (bad path, unknown hotspot, failing baseline)."""


def _load_profile_fn() -> Callable[..., dict] | None:
    from optimizer import profiler

    return getattr(profiler, "profile_workload", None)


@dataclass
class RunConfig:
    path: str
    workload: str | None = None
    test: str | None = None
    passes: int = 1
    hotspots: tuple[str, ...] = ()
    yes: bool = False
    min_improvement: float = 0.05
    timeout: int = 300
    iterations: int = 1
    client: object | None = None
    measure_fn: Callable[[str, Path, int, int], dict] | None = None
    profile_fn: Callable[..., dict] | None = field(default_factory=_load_profile_fn)


@dataclass
class RunResult:
    exit_code: int
    report: dict | None = None
    passes: list[dict] = field(default_factory=list)
    applied_any: bool = False
    declined: bool = False

    def to_json(self) -> dict:
        return {
            "exit_code": self.exit_code,
            "applied": self.applied_any,
            "declined": self.declined,
            "report": self.report,
            "passes": self.passes,
        }


# --------------------------------------------------------------------------- #
# measurement and hotspots
# --------------------------------------------------------------------------- #


def measure(workload: str, root: Path, iterations: int = 1, timeout: int = 300) -> dict:
    """One timing shape for baseline, candidates and re-baseline."""
    return benchmark_workload(workload, cwd=str(root), iterations=iterations, timeout=timeout)


def workload_file(workload: str | None) -> str | None:
    """The script a workload command runs, so it is never picked as a hotspot."""
    if not workload:
        return None
    try:
        tokens = shlex.split(workload)
    except ValueError:
        tokens = workload.split()
    for tok in tokens:
        if tok.endswith(".py"):
            return Path(tok).as_posix().removeprefix("./")
    return None


def build_hotspot(scanner: ProjectScanner, node, metrics: dict | None = None) -> dict:
    """A Hotspot-shaped dict: scanner context plus the profiler's numbers (or None)."""
    ctx = scanner.get_code_context(node.qualified_name)
    metrics = metrics or {}
    return {
        "function": node.name,
        "qualified_name": node.qualified_name,
        "file": node.file_path,
        "line": node.line_start,
        "calls": metrics.get("calls"),
        "self_time": metrics.get("self_time"),
        "cumulative_time": metrics.get("cumulative_time"),
        "runtime_percent": metrics.get("runtime_percent"),
        "dependencies": [d for d in ctx.dependencies if d in scanner.functions],
        "related_files": list(ctx.related_files),
        "source": "profiler" if metrics else "manual",
    }


def _profiled_hotspots(scanner: ProjectScanner, config: RunConfig, root: Path) -> list[dict]:
    if config.profile_fn is None or not config.workload:
        return []
    prof = config.profile_fn(config.workload, cwd=str(root), timeout=config.timeout)
    if not prof or prof.get("exit_code", 0) != 0:
        return []
    skip_file = workload_file(config.workload)
    out = []
    for h in prof.get("hotspots") or []:
        node = scanner.find_function_by_location(h.get("file", ""), int(h.get("line", 0)))
        if node is None or node.file_path == skip_file:
            continue
        if node.file_path.startswith("tests/") or Path(node.file_path).name.startswith("test_"):
            continue
        out.append(build_hotspot(scanner, node, h))
    return out


def resolve_hotspot(
    scanner: ProjectScanner, config: RunConfig, root: Path, pass_number: int, done: set[str]
) -> dict | None:
    """Manual names first (in order, one per pass), then the profiler's ranking."""
    if pass_number - 1 < len(config.hotspots):
        name = config.hotspots[pass_number - 1]
        node = scanner.find_function(name)
        if node is None:
            raise PipelineError(
                f"Unknown function {name!r}. Run `optimizer inspect {config.path}` to list functions."
            )
        return build_hotspot(scanner, node)
    for h in _profiled_hotspots(scanner, config, root):
        if h["qualified_name"] not in done:
            return h
    return None


def project_summary(scanner: ProjectScanner, root: Path) -> dict:
    files = {n.file_path for n in scanner.functions.values()}
    loc = 0
    for rel in files:
        try:
            loc += sum(1 for _ in (root / rel).open(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    return {**scanner.summary(), "loc": loc}


def _scan(config: RunConfig, console: Console) -> tuple[Path, ProjectScanner]:
    root = Path(config.path).resolve()
    if not root.is_dir():
        raise PipelineError(f"Not a directory: {config.path}")
    console.print("Scanning repository...")
    scanner = ProjectScanner(str(root)).scan()
    s = scanner.summary()
    console.print(f"{s['files']} Python files found")
    console.print(f"{s['functions']} functions indexed")
    for err in scanner.errors:
        console.warn(f"skipped: {err}")
    if not scanner.functions:
        raise PipelineError("No Python functions found; nothing to optimize.")
    return root, scanner


def _tail(text: str, lines: int = 15) -> str:
    return "\n".join(text.rstrip().split("\n")[-lines:])


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #


def run(config: RunConfig, console: Console, confirm: Callable[[], bool]) -> RunResult:
    try:
        return _run(config, console, confirm)
    except PipelineError as exc:
        console.error(str(exc))
        return RunResult(EXIT_FAILED)


def _run(config: RunConfig, console: Console, confirm: Callable[[], bool]) -> RunResult:
    if not config.workload:
        raise PipelineError("A --workload command is required to measure anything.")
    root, scanner = _scan(config, console)
    timing = config.measure_fn or measure

    console.print()
    if config.test:
        console.print(f"Running tests: {config.test}")
        baseline_tests = run_tests(config.test, root, timeout=config.timeout)
        if not baseline_tests["passed"]:
            console.print(_tail(baseline_tests["output"]))
            raise PipelineError("Tests fail before any change. Fix them first, or omit --test.")
        console.print(_tests_line(baseline_tests))
    else:
        baseline_tests = None
        console.warn(NO_TESTS_WARNING)

    console.print()
    console.print(f"Running workload: {config.workload}")
    base = timing(config.workload, root, config.iterations, config.timeout)
    if base.get("exit_code", 0) != 0:
        console.print(_tail(base.get("output", "")))
        raise PipelineError("Workload failed at baseline; nothing to compare against.")
    initial_ms = baseline_ms = current_ms = float(base["runtime_ms"])
    console.print(f"Baseline: {_ms(baseline_ms)}")

    try:
        client = config.client or get_llm_client()
    except ValueError as exc:
        raise PipelineError(str(exc)) from exc
    console.print(f"LLM client: {type(client).__name__}")

    passes: list[dict] = []
    done: set[str] = set()
    applied_any = False
    declined = False

    for pass_number in range(1, config.passes + 1):
        console.print()
        if config.passes > 1:
            console.heading(f"PASS {pass_number}")
        hotspot = resolve_hotspot(scanner, config, root, pass_number, done)
        if hotspot is None:
            console.print(NO_HOTSPOT_MESSAGE)
            break
        done.add(hotspot["qualified_name"])
        console.print(format_hotspot(hotspot))
        console.print()
        console.print("Generating candidates...")
        candidates = [c.to_dict() for c in generate_candidates(hotspot, base_dir=str(root), client=client)]
        if not candidates:
            console.warn("No candidates generated.")
            passes.append(pass_report(hotspot, baseline_ms, [], None, False, pass_number))
            continue

        results = []
        for cand in candidates:
            console.print()
            r = evaluate_candidate(
                root,
                cand,
                test_command=config.test,
                benchmark=lambda cwd: timing(config.workload, Path(cwd), config.iterations, config.timeout),
                baseline_ms=baseline_ms,
                min_improvement=config.min_improvement,
                test_timeout=config.timeout,
            )
            results.append(r)
            console.candidate(format_candidate(r))

        winner = choose_winner(results)
        console.print()
        if winner is None:
            pr = pass_report(hotspot, baseline_ms, results, None, False, pass_number)
            console.print(format_winner(pr))
            passes.append(pr)
            continue

        preview = pass_report(hotspot, baseline_ms, results, winner, False, pass_number)
        _print_winner(console, preview)
        console.print()
        applied = config.yes or confirm()
        if not applied:
            declined = True
            console.warn("Not applied.")
            passes.append(preview)
            break

        apply_winner(root, winner)
        applied_any = True
        current_ms = float(winner["benchmark"]["after_ms"])
        console.ok(f"Applied {winner['candidate_id']}.")
        passes.append(pass_report(hotspot, baseline_ms, results, winner, True, pass_number))

        if pass_number < config.passes:
            console.print()
            console.print("Re-profiling...")
            again = timing(config.workload, root, config.iterations, config.timeout)
            if again.get("exit_code", 0) == 0:
                baseline_ms = current_ms = float(again["runtime_ms"])

    final_tests = baseline_tests
    if applied_any and config.test:
        console.print()
        console.print(f"Running tests: {config.test}")
        final_tests = run_tests(config.test, root, timeout=config.timeout)
        console.print(_tests_line(final_tests))

    fr = final_report(project_summary(scanner, root), initial_ms, current_ms, passes, tests=final_tests)
    console.print()
    from optimizer.verifier import format_report

    console.print(format_report(fr))

    code = EXIT_OK if (applied_any or declined) else EXIT_NOTHING_APPLIED
    return RunResult(code, report=fr, passes=passes, applied_any=applied_any, declined=declined)


def _print_winner(console: Console, pr: dict) -> None:
    text = format_winner({**pr, "applied": True}, show_diff=False)  # shown before the prompt; no "(not applied)"
    console.heading(text.split("\n", 1)[0])
    console.print(text.split("\n", 1)[1] if "\n" in text else "")
    if pr.get("diff"):
        console.print()
        console.diff(pr["diff"])
    expl = (pr.get("winner") or {}).get("explanation")
    if expl:
        console.print()
        console.print(f"Why this is faster:\n{expl}")


def _tests_line(tests: dict) -> str:
    if tests.get("total") is not None:
        return f"Tests: {tests['passed_count']}/{tests['total']} passed"
    return "Tests: passed" if tests.get("passed") else "Tests: failed"


def _ms(ms: float) -> str:
    return f"{ms / 1000:.2f} sec" if ms >= 1000 else f"{ms:.0f} ms"


# --------------------------------------------------------------------------- #
# inspect
# --------------------------------------------------------------------------- #


def inspect(config: RunConfig, console: Console, top: int = 3) -> dict:
    try:
        root, scanner = _scan(config, console)
    except PipelineError as exc:
        console.error(str(exc))
        return {"exit_code": EXIT_FAILED}

    hotspots: list[dict] = []
    label = ""
    if config.hotspots:
        for name in config.hotspots:
            node = scanner.find_function(name)
            if node is None:
                console.error(f"Unknown function {name!r}.")
                return {"exit_code": EXIT_FAILED}
            hotspots.append(build_hotspot(scanner, node))
    else:
        if config.workload and config.profile_fn is not None:
            console.print()
            console.print("Profiling execution...")
            hotspots = _profiled_hotspots(scanner, config, root)[:top]
        if not hotspots:
            label = "(static view: no profiler data; ranked by cross-file dependencies)"
            skip = workload_file(config.workload)
            everything = [build_hotspot(scanner, n) for n in scanner.functions.values() if n.file_path != skip]
            everything.sort(key=lambda h: -len(h["dependencies"]))
            hotspots = everything[:top]

    console.print()
    console.heading("Performance opportunities")
    if label:
        console.print(label)
    for h in hotspots:
        console.print()
        console.print(format_hotspot(h))
        if h["related_files"]:
            console.print("\nAffected files:\n" + "\n".join(f"- {f}" for f in h["related_files"]))

    return {"exit_code": EXIT_OK, **project_summary(scanner, root), "hotspots": hotspots}
