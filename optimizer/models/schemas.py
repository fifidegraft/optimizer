"""Shared data models for the Optimizer pipeline.

Every module (scanner, profiler, agent, verifier) passes these objects
around, so this file should not change without the whole team agreeing.
"""
from dataclasses import dataclass, field
from typing import List, Dict


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
