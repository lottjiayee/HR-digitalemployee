"""Public interface Module 4 exposes downstream (consumed by Module 5, Module 7)."""

from __future__ import annotations

from hr_digital_employee.fairness_compliance.access_requests import AccessRequestService
from hr_digital_employee.fairness_compliance.adverse_impact import (
    AdverseImpactTestingService,
    four_fifths_test,
    standardized_difference_test,
)
from hr_digital_employee.fairness_compliance.consent import PICS_NOTICE, ConsentService
from hr_digital_employee.fairness_compliance.explainability import Explanation, explain_score
from hr_digital_employee.fairness_compliance.models import (
    AccessRequest,
    AccessRequestKind,
    AccessRequestStatus,
    ConsentRecord,
    ConsentType,
    DemographicRecord,
    FourFifthsResult,
    GroupOutcome,
    Jurisdiction,
    ProtectedCharacteristic,
    SignificanceResult,
)
from hr_digital_employee.fairness_compliance.skill_ontology_store import SkillOntologyRepository

__all__ = [
    "PICS_NOTICE",
    "AccessRequest",
    "AccessRequestKind",
    "AccessRequestService",
    "AccessRequestStatus",
    "AdverseImpactTestingService",
    "ConsentRecord",
    "ConsentService",
    "ConsentType",
    "DemographicRecord",
    "Explanation",
    "FourFifthsResult",
    "GroupOutcome",
    "Jurisdiction",
    "ProtectedCharacteristic",
    "SignificanceResult",
    "SkillOntologyRepository",
    "explain_score",
    "four_fifths_test",
    "standardized_difference_test",
]
