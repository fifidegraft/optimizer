"""Run the project's test command and report the outcome.

    result = run_tests("pytest -q", cwd=project_root)
    result["passed"]   # bool: exit code 0

A failing suite is a normal outcome (the candidate gets rejected), so this
never raises for non-zero exits or timeouts. Only a missing/invalid cwd raises.

Result dict:
    {"command": "pytest -q", "passed": False, "skipped": False, "timed_out": False,
     "exit_code": 1, "duration_ms": 812.4,
     "total": 34, "passed_count": 32, "failed": 2,   # from pytest's summary; None if unknown
     "output": "<tail of stdout+stderr>"}
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

OUTPUT_TAIL_CHARS = 10_000

# pytest summary line. Verbose: "===== 2 failed, 32 passed in 1.23s =====".
# Quiet (-q): "2 failed, 32 passed in 1.23s" with no bars.
_COUNT_RE = re.compile(
    r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed|warnings?|deselected)\b"
)
_SUMMARY_LINE_RE = re.compile(
    r"^(?:=+\s*)?"
    r"(?:\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed|warnings?|deselected)(?:, )?)+"
    r"\s+in\s+[\d.]+\s*s\b.*?(?:\s*=+)?$"
)


def parse_pytest_summary(output: str) -> dict:
    """Extract counts from pytest output. Returns None-valued fields if no summary found."""
    counts: dict[str, int] = {}
    for line in reversed(output.splitlines()):
        line = line.strip()
        if _SUMMARY_LINE_RE.match(line):
            for n, kind in _COUNT_RE.findall(line):
                kind = "error" if kind == "errors" else kind
                counts[kind] = counts.get(kind, 0) + int(n)
            break
    if not counts:
        return {"total": None, "passed_count": None, "failed": None}
    failed = counts.get("failed", 0) + counts.get("error", 0)
    passed = counts.get("passed", 0)
    return {"total": passed + failed, "passed_count": passed, "failed": failed}


def run_tests(command: str | None, cwd: str | Path, timeout: float = 600) -> dict:
    """Run `command` in `cwd` via the shell and report whether it passed.

    command=None means the user gave no test command: returns passed=True with
    skipped=True so callers can warn that behavior was not verified.
    """
    if command is None or not command.strip():
        return {
            "command": "",
            "passed": True,
            "skipped": True,
            "timed_out": False,
            "exit_code": 0,
            "duration_ms": 0.0,
            "total": None,
            "passed_count": None,
            "failed": None,
            "output": "",
        }

    cwd = Path(cwd)
    if not cwd.is_dir():
        raise NotADirectoryError(str(cwd))

    start = time.perf_counter()
    timed_out = False
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        exit_code = proc.returncode
        output = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = -1
        output = _decode(exc.stdout) + _decode(exc.stderr) + f"\n[timed out after {timeout}s]"
    duration_ms = (time.perf_counter() - start) * 1000

    counts = parse_pytest_summary(output)
    return {
        "command": command,
        "passed": exit_code == 0 and not timed_out,
        "skipped": False,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        **counts,
        "output": output[-OUTPUT_TAIL_CHARS:],
    }


def _decode(data: bytes | str | None) -> str:
    if data is None:
        return ""
    return data.decode(errors="replace") if isinstance(data, bytes) else data
