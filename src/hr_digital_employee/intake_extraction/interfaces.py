"""Public interface Module 1 exposes downstream (consumed by Module 2 and others)."""

from __future__ import annotations

from hr_digital_employee.intake_extraction.models import (
    Candidate,
    ExtractedField,
    ExtractedResume,
    FieldStatus,
)

__all__ = ["Candidate", "ExtractedField", "ExtractedResume", "FieldStatus"]
