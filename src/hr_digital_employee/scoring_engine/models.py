"""Domain models for the Scoring Engine (design.md §3.4; FR-6, FR-7, FR-8, FR-31, NFR-5).

A JRP has two independent kinds of criteria (GLOSSARY.md "Must-have vs. weighted criteria"):
must-have criteria are pure pass/fail gates and never contribute a score; weighted criteria each
map to one of the four scored dimensions and contribute proportionally once the gates pass. See
ASSUMPTIONS.md for why this split, rather than letting any of the four dimensions itself be
tagged must-have, was the interpretation picked for this draft.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field

SCORING_ENGINE_VERSION = "stub-0.1.0"
"""NFR-5: stamped on every Score record. Bump when the scoring math changes."""


class Dimension(enum.Enum):
    MANDATORY_SKILLS = "mandatory_skills"
    EXPERIENCE_TENURE = "experience_tenure"
    EDUCATIONAL_LEVEL = "educational_level"
    PROJECT_RELEVANCE = "project_relevance"


class MatchingCurve(enum.Enum):
    LINEAR = "linear"
    STEP = "step"
    BUFFERED = "buffered"


class Tier(enum.Enum):
    HIGH_MATCH = "high_match"
    MID_MATCH = "mid_match"
    LOW_MATCH = "low_match"


class EducationLevel(enum.IntEnum):
    """Ordinal so a candidate/required pair can form a ratio (BACHELOR / MASTER = 0.75, etc.)."""

    NONE = 0
    HIGH_SCHOOL = 1
    ASSOCIATE = 2
    BACHELOR = 3
    MASTER = 4
    DOCTORATE = 5


@dataclass(frozen=True)
class TierThresholds:
    """FR-31: defaults ship as High 80-100 / Mid 60-79 / Low <60, configurable per JRP."""

    high_match_min: float = 80.0
    mid_match_min: float = 60.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.mid_match_min <= self.high_match_min <= 100.0):
            raise ValueError(
                "tier thresholds must satisfy 0 <= mid_match_min <= high_match_min <= 100, "
                f"got mid={self.mid_match_min}, high={self.high_match_min}"
            )

    def classify(self, total_score: float) -> Tier:
        if total_score >= self.high_match_min:
            return Tier.HIGH_MATCH
        if total_score >= self.mid_match_min:
            return Tier.MID_MATCH
        return Tier.LOW_MATCH


class WeightTemplate(enum.Enum):
    GENERAL = "general"
    SENIOR_TECHNICAL = "senior_technical"
    JUNIOR_GRADUATE = "junior_graduate"
    MANAGERIAL = "managerial"
    LICENSED_COMPLIANCE = "licensed_compliance"


class MustHaveKind(enum.Enum):
    REQUIRED_SKILL = "required_skill"
    MINIMUM_YEARS_EXPERIENCE = "minimum_years_experience"


@dataclass(frozen=True)
class MustHaveCriterion:
    """A pass/fail gate (module-2-scoring-engine.md §4: "no score is computed" on failure).

    Module-2 doc §4 guidance: trainable skills should not be must-have -- this type only models
    a required skill or an experience floor, not an arbitrary rule DSL, to keep that guidance easy
    to follow rather than easy to violate.
    """

    kind: MustHaveKind
    label: str
    required_skill: str | None = None
    minimum_years: float | None = None

    def __post_init__(self) -> None:
        # A blank/missing label parsed fine here and was accepted as a "valid" JRP by
        # config_builder.py's validate_jrp_dict -- a plausible JRP-editor fat-finger (one blank
        # grid cell) that then crashed both cli.py and the dashboard the moment any candidate
        # actually failed the criterion: `"; ".join(score.failed_must_have_labels)` raises
        # TypeError on a None/non-string label. Caught here instead, at construction, the same
        # "parses fine, crashes later in a different module" pattern already guarded for
        # `minimum_years`/`version` elsewhere in this file.
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError(f"label must be a non-empty string, got {self.label!r}")
        if self.kind is MustHaveKind.REQUIRED_SKILL and not self.required_skill:
            raise ValueError("REQUIRED_SKILL must-have criteria need required_skill set")
        if self.kind is MustHaveKind.MINIMUM_YEARS_EXPERIENCE:
            if self.minimum_years is None:
                raise ValueError(
                    "MINIMUM_YEARS_EXPERIENCE must-have criteria need minimum_years set"
                )
            # A non-numeric value here (e.g. a YAML author typing "five" instead of 5) would
            # otherwise parse successfully and only crash later, mid-scoring, when engine.py
            # compares a candidate's years against it -- caught here instead, at construction.
            if isinstance(self.minimum_years, bool) or not isinstance(
                self.minimum_years, (int, float)
            ):
                raise TypeError(f"minimum_years must be a number, got {self.minimum_years!r}")
            # `nan < 0` is False and `inf > 0` is True, so neither is caught by a negativity check
            # alone -- a YAML typo like `minimum_years: .nan` sailed through silently, then made
            # `years_of_experience >= minimum_years` False for every candidate forever (NaN
            # comparisons are always false); `.inf` made it False for every *finite* candidate,
            # forever -- both a permanent, invisible must-have gate with no config-load error ever
            # flagging it.
            if not math.isfinite(self.minimum_years):
                raise ValueError(f"minimum_years must be finite, got {self.minimum_years}")
            if self.minimum_years < 0:
                raise ValueError(f"minimum_years cannot be negative, got {self.minimum_years}")


@dataclass(frozen=True)
class WeightedCriterion:
    """One of the four scored dimensions: a weight (percentage points), a matching curve, and the
    requirement value that curve measures the candidate against. Only the requirement field(s)
    matching `dimension` are meaningful -- see `__post_init__`."""

    dimension: Dimension
    weight: float
    curve: MatchingCurve
    required_skills: tuple[str, ...] = ()
    required_years: float | None = None
    required_education_level: EducationLevel | None = None
    required_project_count: int | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.weight <= 100.0:
            raise ValueError(f"weight must be in [0, 100], got {self.weight}")
        if self.dimension is Dimension.MANDATORY_SKILLS and not self.required_skills:
            raise ValueError("MANDATORY_SKILLS criterion needs at least one required skill")
        if self.dimension is Dimension.EXPERIENCE_TENURE and not (
            self.required_years is not None
            and math.isfinite(self.required_years)
            and self.required_years > 0
        ):
            # `inf > 0` is True, so a bare positivity check let `required_years: .inf` through --
            # confirmed this makes curve_score permanently 0.0 for any finite candidate, with no
            # config-load error despite `.inf` being a nonsensical requirement value.
            raise ValueError("EXPERIENCE_TENURE criterion needs a finite, positive required_years")
        if self.dimension is Dimension.EDUCATIONAL_LEVEL and self.required_education_level is None:
            raise ValueError("EDUCATIONAL_LEVEL criterion needs a required_education_level")
        if self.dimension is Dimension.PROJECT_RELEVANCE and not (
            self.required_project_count is not None
            and math.isfinite(self.required_project_count)
            and self.required_project_count > 0
        ):
            raise ValueError(
                "PROJECT_RELEVANCE criterion needs a finite, positive required_project_count"
            )


@dataclass(frozen=True)
class JRP:
    """Job Requirement Profile: one per role, versioned (FR-6). Weighted criteria weights must sum
    to 100; each dimension may appear at most once among them."""

    jrp_id: str
    role_name: str
    version: int
    weight_template: WeightTemplate
    weighted_criteria: tuple[WeightedCriterion, ...]
    must_have_criteria: tuple[MustHaveCriterion, ...] = ()
    tier_thresholds: TierThresholds = field(default_factory=TierThresholds)

    def __post_init__(self) -> None:
        # A quoted YAML scalar (`version: "1"`) parses fine as a str -- nothing here or in
        # jrp_config.py checked its type, so it wasn't caught until JRPRepository.save()'s
        # monotonicity check (`jrp.version <= existing.version`) crashed with an uncaught
        # `TypeError: '<=' not supported between instances of 'int' and 'str'` the moment a
        # second, differently-typed version was saved -- the same "parses fine, crashes later in a
        # different module" pattern already fixed here for `minimum_years`/`tier_thresholds`.
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise ValueError(f"version must be an int, got {self.version!r}")
        total_weight = sum(criterion.weight for criterion in self.weighted_criteria)
        if not math.isclose(total_weight, 100.0, abs_tol=0.01):
            raise ValueError(
                f"weighted criteria weights must sum to 100, got {total_weight} for JRP "
                f"{self.jrp_id!r}"
            )
        dimensions = [criterion.dimension for criterion in self.weighted_criteria]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError(
                f"each dimension may appear at most once in weighted_criteria, got {dimensions}"
            )


EDUCATIONAL_LEVEL_WEIGHT_GUIDELINE_MAX = 15.0
"""Module-2 doc §4: "Educational Level weight defaults to <=15%" -- guidance, not a hard system
constraint, but "should be enforced as a default/warning" (see `weight_guideline_warnings`)."""


def weight_guideline_warnings(jrp: JRP) -> tuple[str, ...]:
    """Non-blocking guidance warnings for a JRP -- module-2 doc §4: Educational Level weight over
    the guideline default should surface a warning, not reject the JRP outright."""
    warnings: list[str] = []
    for criterion in jrp.weighted_criteria:
        if (
            criterion.dimension is Dimension.EDUCATIONAL_LEVEL
            and criterion.weight > EDUCATIONAL_LEVEL_WEIGHT_GUIDELINE_MAX
        ):
            warnings.append(
                f"Educational Level weight is {criterion.weight}%, above the "
                f"{EDUCATIONAL_LEVEL_WEIGHT_GUIDELINE_MAX}% guideline default"
            )
    return tuple(warnings)


@dataclass(frozen=True)
class CandidateProfile:
    """The Scoring Engine's own structured input contract -- deliberately not Module 1's
    `ExtractedResume` directly. See ASSUMPTIONS.md: mapping Module 1's free-text fields into these
    typed values (parsing "5 years" out of an experience paragraph, ranking a degree string into an
    `EducationLevel`) is a separate, still-open integration step from the scoring math itself."""

    skills: tuple[str, ...]
    years_of_experience: float
    education_level: EducationLevel
    project_count: int

    def __post_init__(self) -> None:
        # `nan < 0` is False, so a NaN would otherwise sail past this check, then silently poison
        # every curve/total-score computation downstream with no exception anywhere (FR-9:
        # nothing in this deterministic module should silently produce a wrong result).
        if math.isnan(self.years_of_experience) or self.years_of_experience < 0:
            raise ValueError(
                f"years_of_experience cannot be negative or NaN, got {self.years_of_experience}"
            )
        if self.project_count < 0:
            raise ValueError(f"project_count cannot be negative, got {self.project_count}")


@dataclass(frozen=True)
class DimensionResult:
    """One line of the Matching Analysis breakdown (FR-11, FR-25)."""

    dimension: Dimension
    raw_ratio: float
    curve_score: float
    weight: float
    contribution: float


@dataclass(frozen=True)
class Score:
    """Immutable once produced (design.md §4.1) -- a new engine/JRP version means a new Score
    record, never an overwrite. NFR-5 requires both the scoring-engine and the parser version that
    produced the extraction feeding this score."""

    jrp_id: str
    jrp_version: int
    scoring_engine_version: str
    parser_version: str
    total_score: float
    tier: Tier
    passed_must_have: bool
    failed_must_have_labels: tuple[str, ...]
    breakdown: tuple[DimensionResult, ...]
