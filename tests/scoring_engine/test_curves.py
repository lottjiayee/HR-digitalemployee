"""Tests for matching curves (test.md T2.5-T2.7)."""

from __future__ import annotations

from hr_digital_employee.scoring_engine.curves import apply_curve
from hr_digital_employee.scoring_engine.models import MatchingCurve


def test_t2_5_linear_curve_gives_proportional_credit() -> None:
    # 4 of 5 required years
    assert apply_curve(MatchingCurve.LINEAR, 4 / 5) == 0.8


def test_linear_curve_caps_at_full_credit_when_exceeding_requirement() -> None:
    assert apply_curve(MatchingCurve.LINEAR, 6 / 5) == 1.0


def test_t2_6_step_curve_gives_zero_credit_below_requirement() -> None:
    assert apply_curve(MatchingCurve.STEP, 4 / 5) == 0.0


def test_step_curve_gives_full_credit_at_or_above_requirement() -> None:
    assert apply_curve(MatchingCurve.STEP, 1.0) == 1.0
    assert apply_curve(MatchingCurve.STEP, 1.2) == 1.0


def test_t2_7_buffered_curve_gives_high_credit_close_to_requirement() -> None:
    # 4 of 5 required years -- ratio 0.8 is exactly the "close" band
    assert apply_curve(MatchingCurve.BUFFERED, 4 / 5) == 0.9


def test_buffered_curve_gives_full_credit_at_or_above_requirement() -> None:
    assert apply_curve(MatchingCurve.BUFFERED, 1.0) == 1.0


def test_buffered_curve_degrades_further_below_the_close_band() -> None:
    half_credit = apply_curve(MatchingCurve.BUFFERED, 0.4)
    zero_credit = apply_curve(MatchingCurve.BUFFERED, 0.0)

    assert 0.0 < half_credit < 0.9
    assert zero_credit == 0.0
