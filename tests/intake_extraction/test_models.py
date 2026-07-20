"""Tests for intake_extraction domain models."""

from __future__ import annotations

import pytest

from hr_digital_employee.intake_extraction.models import ExtractedField, FieldStatus


def test_confidence_must_be_between_zero_and_one() -> None:
    with pytest.raises(ValueError, match="confidence must be in"):
        ExtractedField(value="x", confidence=1.5, status=FieldStatus.VERIFIED)


def test_meets_must_have_confidence_true_when_verified_and_above_threshold() -> None:
    field_ = ExtractedField(value="x", confidence=0.9, status=FieldStatus.VERIFIED)
    assert field_.meets_must_have_confidence is True


def test_meets_must_have_confidence_false_when_below_threshold() -> None:
    field_ = ExtractedField(value="x", confidence=0.5, status=FieldStatus.VERIFIED)
    assert field_.meets_must_have_confidence is False


def test_meets_must_have_confidence_false_when_unverified_even_if_confidence_high() -> None:
    field_: ExtractedField[str] = ExtractedField(
        value=None, confidence=0.9, status=FieldStatus.UNVERIFIED
    )
    assert field_.meets_must_have_confidence is False
