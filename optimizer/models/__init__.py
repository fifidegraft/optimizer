"""Shared data models for all Optimizer modules."""

from .schemas import (
    WorkloadResult,
    Hotspot,
    CandidateOptimization,
    OptimizationPass,
)

__all__ = [
    "WorkloadResult",
    "Hotspot",
    "CandidateOptimization",
    "OptimizationPass",
]
