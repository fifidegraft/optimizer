"""Shared fixtures for the CLI tests.

A tiny two-file project with a pure, cacheable hotspot (`lib.parse`) and a
workload that calls it repeatedly with repeated inputs, so the agent's offline
mock candidate (lru_cache) produces a real, measurable win.
"""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

import pytest

from optimizer.agent import BaseLLMClient

PY = shlex.quote(sys.executable)

LIB = '''\
"""Toy library with one deliberately slow, pure function."""


def parse(text):
    total = 0
    for _ in range(3000):
        for ch in text:
            total = (total * 31 + ord(ch)) % 1000003
    return total


def summarize(items):
    return [parse(x) for x in items]
'''

BENCH = """\
from lib import summarize

items = [f"item-{i}" for i in range(10)] * 60
print(sum(summarize(items)))
"""

WORKLOAD = f"{PY} bench.py"
TESTS_PASS = f'{PY} -c "from lib import parse; assert parse(\'ab\') == parse(\'ab\'); assert parse(\'a\') != parse(\'b\')"'
TESTS_FAIL = f'{PY} -c "import sys; sys.exit(1)"'


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "lib.py").write_text(LIB)
    (tmp_path / "bench.py").write_text(BENCH)
    return tmp_path


class StubClient(BaseLLMClient):
    """Returns scripted candidate payloads, one list per call (the last repeats)."""

    def __init__(self, *rounds: list[dict]):
        self.rounds = list(rounds)
        self.calls = 0

    def generate_raw(self, prompt: str, system_prompt: str) -> str:
        self.calls += 1
        current = self.rounds.pop(0) if len(self.rounds) > 1 else self.rounds[0]
        return json.dumps({"candidates": current})


def candidate(cid: str, content: str, path: str = "lib.py", strategy: str = "stub") -> dict:
    return {
        "candidate_id": cid,
        "strategy": strategy,
        "explanation": f"{cid} explanation",
        "edits": [{"path": path, "new_content": content}],
    }


def fake_measure(*runtimes_ms: float, exit_code: int = 0):
    """Scripted timings; the last value repeats. Records every cwd it was called with."""
    seq = list(runtimes_ms)
    calls: list[Path] = []

    def run(workload: str, root: Path, iterations: int, timeout: int) -> dict:
        calls.append(Path(root))
        value = seq.pop(0) if len(seq) > 1 else seq[0]
        return {"runtime_ms": value, "exit_code": exit_code, "output": f"Runtime: {value} ms"}

    run.calls = calls
    return run


def fake_profiler(*hotspots: dict, exit_code: int = 0):
    calls: list[str] = []

    def profile(command: str, cwd: str = ".", timeout: int = 300, limit: int = 20) -> dict:
        calls.append(command)
        return {"exit_code": exit_code, "output": "", "hotspots": list(hotspots)}

    profile.calls = calls
    return profile
