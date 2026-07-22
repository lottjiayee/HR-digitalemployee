"""Public interface Module 2 exposes downstream (consumed by Module 3, Module 4, Module 5)."""

from __future__ import annotations

from hr_digital_employee.scoring_engine.engine import ScoringEngine
from hr_digital_employee.scoring_engine.models import (
    JRP,
    CandidateProfile,
    Dimension,
    DimensionResult,
    Score,
    Tier,
)

__all__ = [
    "JRP",
    "CandidateProfile",
    "Dimension",
    "DimensionResult",
    "Score",
    "ScoringEngine",
    "Tier",
]
