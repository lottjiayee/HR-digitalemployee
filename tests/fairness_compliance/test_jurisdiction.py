"""Tests for jurisdiction layering (module-4 doc §4)."""

from __future__ import annotations

from hr_digital_employee.fairness_compliance.jurisdiction import (
    STRICTEST_DEFAULT,
    resolve_jurisdiction,
)
from hr_digital_employee.fairness_compliance.models import Jurisdiction


def test_undetermined_jurisdiction_defaults_to_the_strictest_framework() -> None:
    assert resolve_jurisdiction(Jurisdiction.UNDETERMINED) is STRICTEST_DEFAULT


def test_a_known_jurisdiction_is_returned_unchanged() -> None:
    assert resolve_jurisdiction(Jurisdiction.HK_PDPO) is Jurisdiction.HK_PDPO
    assert resolve_jurisdiction(Jurisdiction.CHINA_PIPL) is Jurisdiction.CHINA_PIPL
