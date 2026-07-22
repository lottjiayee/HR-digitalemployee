"""Domain models for Fairness & Compliance (design.md §3.6; FR-20-23, FR-25-27, FR-30)."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime


class ProtectedCharacteristic(enum.Enum):
    """Hong Kong ordinances this module tests against (module-4 doc §4)."""

    SEX = "sex"
    MARITAL_STATUS = "marital_status"
    PREGNANCY = "pregnancy"
    FAMILY_STATUS = "family_status"
    DISABILITY = "disability"
    RACE = "race"


@dataclass(frozen=True)
class DemographicRecord:
    """Voluntary, self-declared (FR-21) -- stored only here, never a Scoring Engine input. See
    tests/test_architectural_invariants.py for the enforced import-direction separation."""

    candidate_id: str
    characteristic: ProtectedCharacteristic
    value: str
    declared_at: datetime


@dataclass(frozen=True)
class GroupOutcome:
    """One protected-characteristic group's selection-rate inputs for one JRP (aggregate-only --
    never reconstructs an individual's protected attributes, per FR-21)."""

    group_label: str
    selected_count: int
    total_count: int

    def __post_init__(self) -> None:
        if self.total_count <= 0:
            raise ValueError(f"total_count must be positive, got {self.total_count}")
        if not 0 <= self.selected_count <= self.total_count:
            raise ValueError(
                f"selected_count ({self.selected_count}) must be between 0 and "
                f"total_count ({self.total_count})"
            )

    @property
    def selection_rate(self) -> float:
        return self.selected_count / self.total_count


@dataclass(frozen=True)
class FourFifthsResult:
    """FR-20: flags if any group's selection rate is below 80% of the highest group's rate. A
    trigger for human review, not a verdict -- see `SignificanceResult`."""

    flagged: bool
    lowest_rate_group: str
    highest_rate_group: str
    impact_ratio: float


@dataclass(frozen=True)
class SignificanceResult:
    """Statistical corroboration of a four-fifths flag (module-4 doc §4: "corroborate with a
    significance test... before concluding anything")."""

    z_score: float
    significant: bool


class ConsentType(enum.Enum):
    """FR-22: talent-pool consent is separate and unbundled from application consent."""

    APPLICATION = "application"
    TALENT_POOL = "talent_pool"


@dataclass(frozen=True)
class ConsentRecord:
    candidate_id: str
    consent_type: ConsentType
    granted_at: datetime
    withdrawn_at: datetime | None = None


class Jurisdiction(enum.Enum):
    """module-4 doc §4: PDPO baseline, GDPR for EU candidates, PIPL for Mainland China
    candidates, default to the strictest framework when undetermined."""

    HK_PDPO = "hk_pdpo"
    EU_GDPR = "eu_gdpr"
    CHINA_PIPL = "china_pipl"
    UNDETERMINED = "undetermined"


class AccessRequestKind(enum.Enum):
    ACCESS = "access"
    CORRECTION = "correction"


class AccessRequestStatus(enum.Enum):
    RECEIVED = "received"
    IN_PROGRESS = "in_progress"
    FULFILLED = "fulfilled"


@dataclass(frozen=True)
class AccessRequest:
    """FR-26: a candidate's access-to/correction-of their held data request. Tracks the request
    *lifecycle*, not a mutation of stored candidate data -- no real candidate-data store exists
    yet to fulfill against (see ASSUMPTIONS.md)."""

    request_id: str
    candidate_id: str
    kind: AccessRequestKind
    status: AccessRequestStatus
    requested_at: datetime
    detail: str = ""
