"""Matching curves (FR-8, GLOSSARY.md "Matching curve"): how partial credit is given on a weighted
criterion, given `ratio = candidate_value / required_value`.
"""

from __future__ import annotations

from hr_digital_employee.scoring_engine.models import MatchingCurve

BUFFERED_CLOSE_RATIO = 0.8
"""Ratio at/above which a Buffered curve treats the candidate as "close enough"."""

BUFFERED_CLOSE_CREDIT = 0.9
"""Credit given at BUFFERED_CLOSE_RATIO -- matches the GLOSSARY.md "e.g., 90%" example (a
candidate with 4 of 5 required years, ratio 0.8, scores 90% under Buffered)."""


def apply_curve(curve: MatchingCurve, ratio: float) -> float:
    """Map a raw ratio to a curve-adjusted score in [0, 1]."""
    ratio = max(ratio, 0.0)

    if curve is MatchingCurve.LINEAR:
        return min(ratio, 1.0)

    if curve is MatchingCurve.STEP:
        return 1.0 if ratio >= 1.0 else 0.0

    if curve is MatchingCurve.BUFFERED:
        if ratio >= 1.0:
            return 1.0
        if ratio >= BUFFERED_CLOSE_RATIO:
            return BUFFERED_CLOSE_CREDIT
        return BUFFERED_CLOSE_CREDIT * (ratio / BUFFERED_CLOSE_RATIO)

    raise AssertionError(f"unhandled curve {curve!r}")  # exhaustive over MatchingCurve
