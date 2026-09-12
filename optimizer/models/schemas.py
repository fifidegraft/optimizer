"""Shared data models for the Optimizer pipeline.

Every module (scanner, profiler, agent, verifier) passes these objects
around, so this file should not change without the whole team agreeing.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json


# =====================================================================
# Scanner Models (Joe)
# =====================================================================

@dataclass
class FunctionNode:
    """One function or method found while scanning the repository."""
    name: str                     # bare name, e.g. "generate_feed"
    qualified_name: str           # e.g. "services.recommendations.generate_feed"
    file_path: str
    line_start: int
    line_end: int
    calls: List[str] = field(default_factory=list)  # names this function calls (unresolved)


@dataclass
class CodeContext:
    """Everything the LLM (Person 3) needs to propose an optimization for one hotspot."""
    hotspot_function: str
    file_path: str
    line_start: int
    line_end: int
    code_snippet: str
    dependencies: List[str] = field(default_factory=list)
    related_files: List[str] = field(default_factory=list)
    related_code_snippets: Dict[str, str] = field(default_factory=dict)


# =====================================================================
# Profiler & Hotspot Models (Henry / Emeka)
# =====================================================================

@dataclass
class Hotspot:
    """Represents a performance bottleneck identified by the profiler and scanner."""
    function: str
    qualified_name: str
    file: str
    line: int
    calls: int
    self_time: float
    cumulative_time: float
    runtime_percent: float
    dependencies: List[str] = field(default_factory=list)
    related_files: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Hotspot:
        return cls(
            function=str(data.get("function") or ""),
            qualified_name=str(data.get("qualified_name") or ""),
            file=str(data.get("file") or ""),
            line=int(data.get("line") or 0),
            calls=int(data.get("calls") or 0),
            self_time=float(data.get("self_time") or 0.0),
            cumulative_time=float(data.get("cumulative_time") or 0.0),
            runtime_percent=float(data.get("runtime_percent") or 0.0),
            dependencies=list(data.get("dependencies") or []),
            related_files=list(data.get("related_files") or [])
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =====================================================================
# Agent & Verifier Models (Henry / Fifi)
# =====================================================================

@dataclass
class ModifiedFile:
    """
    Represents an edited file within a candidate patch.
    Matches Fifi's format: {"path": "...", "new_content": "..."}.
    """
    path: str
    new_content: str

    @property
    def content(self) -> str:
        """Alias for backward compatibility."""
        return self.new_content

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModifiedFile:
        return cls(
            path=str(data.get("path") or ""),
            new_content=str(data.get("new_content") or data.get("content") or "")
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "new_content": self.new_content
        }


@dataclass
class CandidatePatch:
    """
    Represents a candidate optimization patch sent to Fifi's Verifier.
    Matches Fifi's requested contract:
    {
        "candidate_id": "candidate_a",
        "strategy": "...",
        "explanation": "...",
        "edits": [{"path": "...", "new_content": "..."}]
    }
    """
    candidate_id: str
    strategy: str
    explanation: str
    edits: List[ModifiedFile] = field(default_factory=list)
    # Verification & benchmarking results populated by Fifi's Verifier directly
    accepted: Optional[bool] = None
    rejection_reason: Optional[str] = None  # "apply_failed" | "tests_failed" | "benchmark_failed" | "slower" | None
    tests: Optional[Dict[str, Any]] = None   # {"passed": True, "total": 34, "passed_count": 34, "failed": 0}
    benchmark: Optional[Dict[str, Any]] = None  # {"before_ms": 840, "after_ms": 191, "speedup": 4.4}

    @property
    def modified_files(self) -> List[ModifiedFile]:
        """Alias for edits."""
        return self.edits

    @property
    def files_changed(self) -> List[str]:
        """Convenience list of file paths."""
        return [e.path for e in self.edits]

    @property
    def tests_passed(self) -> Optional[bool]:
        """Supports Fifi's boolean format or legacy count comparison."""
        if self.tests is not None:
            val = self.tests.get("passed")
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)) and "total" in self.tests:
                return val == self.tests.get("total")
        return None

    @property
    def speedup(self) -> Optional[float]:
        if self.benchmark is not None:
            return self.benchmark.get("speedup")
        return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CandidatePatch:
        raw_edits = data.get("edits") or data.get("modified_files") or []
        edits_list = [
            ModifiedFile.from_dict(f) if isinstance(f, dict) else f
            for f in raw_edits
        ]
        return cls(
            candidate_id=str(data.get("candidate_id") or ""),
            strategy=str(data.get("strategy") or ""),
            explanation=str(data.get("explanation") or ""),
            edits=edits_list,
            accepted=data.get("accepted"),
            rejection_reason=data.get("rejection_reason"),
            tests=data.get("tests"),
            benchmark=data.get("benchmark")
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "strategy": self.strategy,
            "explanation": self.explanation,
            "edits": [e.to_dict() for e in self.edits],
            "files_changed": self.files_changed,
            "accepted": self.accepted,
            "rejection_reason": self.rejection_reason,
            "tests": self.tests,
            "benchmark": self.benchmark
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
