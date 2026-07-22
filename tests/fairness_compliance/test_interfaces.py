"""Confirms Module 4's downstream-facing interface surface is importable and populated."""

from __future__ import annotations

from hr_digital_employee.fairness_compliance.interfaces import (
    PICS_NOTICE,
    AccessRequestKind,
    AccessRequestService,
    ConsentService,
    ConsentType,
    Explanation,
    FourFifthsResult,
    GroupOutcome,
    Jurisdiction,
    ProtectedCharacteristic,
    SignificanceResult,
    SkillOntologyRepository,
    explain_score,
    four_fifths_test,
    standardized_difference_test,
)


def test_downstream_interface_exports_are_the_real_types() -> None:
    assert isinstance(PICS_NOTICE, str) and PICS_NOTICE
    assert AccessRequestKind.ACCESS.value == "access"
    assert AccessRequestService.__name__ == "AccessRequestService"
    assert ConsentService.__name__ == "ConsentService"
    assert ConsentType.TALENT_POOL.value == "talent_pool"
    assert Explanation.__name__ == "Explanation"
    assert FourFifthsResult.__name__ == "FourFifthsResult"
    assert GroupOutcome.__name__ == "GroupOutcome"
    assert Jurisdiction.HK_PDPO.value == "hk_pdpo"
    assert ProtectedCharacteristic.RACE.value == "race"
    assert SignificanceResult.__name__ == "SignificanceResult"
    assert SkillOntologyRepository.__name__ == "SkillOntologyRepository"
    assert callable(explain_score)
    assert callable(four_fifths_test)
    assert callable(standardized_difference_test)
