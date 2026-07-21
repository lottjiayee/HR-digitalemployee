"""Confirms Module 2's downstream-facing interface surface is importable and populated."""

from __future__ import annotations

from hr_digital_employee.scoring_engine.interfaces import (
    JRP,
    CandidateProfile,
    DimensionResult,
    Score,
    ScoringEngine,
    Tier,
)


def test_downstream_interface_exports_are_the_real_types() -> None:
    assert JRP.__name__ == "JRP"
    assert CandidateProfile.__name__ == "CandidateProfile"
    assert DimensionResult.__name__ == "DimensionResult"
    assert Score.__name__ == "Score"
    assert ScoringEngine.__name__ == "ScoringEngine"
    assert Tier.HIGH_MATCH.value == "high_match"
