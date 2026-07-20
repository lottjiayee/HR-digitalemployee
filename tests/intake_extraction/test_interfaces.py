"""Confirms Module 1's downstream-facing interface surface is importable and populated."""

from __future__ import annotations

from hr_digital_employee.intake_extraction.interfaces import (
    Candidate,
    ExtractedField,
    ExtractedResume,
    FieldStatus,
)


def test_downstream_interface_exports_are_the_real_model_types() -> None:
    assert Candidate.__name__ == "Candidate"
    assert ExtractedResume.__name__ == "ExtractedResume"
    assert ExtractedField.__name__ == "ExtractedField"
    assert FieldStatus.VERIFIED.value == "verified"
