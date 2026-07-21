"""The five weight-template presets (FR-6, module-2-scoring-engine.md §3).

HR selects one of these as a JRP's starting point and may fine-tune any weight afterward, as long
as the total across a JRP's weighted criteria still sums to 100 (enforced by `JRP.__post_init__`).
"""

from __future__ import annotations

from hr_digital_employee.scoring_engine.models import (
    Dimension,
    EducationLevel,
    MatchingCurve,
    WeightedCriterion,
    WeightTemplate,
)

_PRESET_WEIGHTS: dict[WeightTemplate, dict[Dimension, float]] = {
    WeightTemplate.GENERAL: {
        Dimension.MANDATORY_SKILLS: 40.0,
        Dimension.EXPERIENCE_TENURE: 30.0,
        Dimension.EDUCATIONAL_LEVEL: 15.0,
        Dimension.PROJECT_RELEVANCE: 15.0,
    },
    WeightTemplate.SENIOR_TECHNICAL: {
        Dimension.MANDATORY_SKILLS: 35.0,
        Dimension.EXPERIENCE_TENURE: 35.0,
        Dimension.EDUCATIONAL_LEVEL: 10.0,
        Dimension.PROJECT_RELEVANCE: 20.0,
    },
    WeightTemplate.JUNIOR_GRADUATE: {
        Dimension.MANDATORY_SKILLS: 45.0,
        Dimension.EXPERIENCE_TENURE: 5.0,
        Dimension.EDUCATIONAL_LEVEL: 30.0,
        Dimension.PROJECT_RELEVANCE: 20.0,
    },
    WeightTemplate.MANAGERIAL: {
        Dimension.MANDATORY_SKILLS: 25.0,
        Dimension.EXPERIENCE_TENURE: 30.0,
        Dimension.EDUCATIONAL_LEVEL: 15.0,
        Dimension.PROJECT_RELEVANCE: 30.0,
    },
    WeightTemplate.LICENSED_COMPLIANCE: {
        Dimension.MANDATORY_SKILLS: 50.0,
        Dimension.EXPERIENCE_TENURE: 20.0,
        Dimension.EDUCATIONAL_LEVEL: 20.0,
        Dimension.PROJECT_RELEVANCE: 10.0,
    },
}


def preset_weights(template: WeightTemplate) -> dict[Dimension, float]:
    """The unmodified default weight for each dimension under `template`."""
    return dict(_PRESET_WEIGHTS[template])


def default_weighted_criterion(
    template: WeightTemplate,
    dimension: Dimension,
    curve: MatchingCurve,
    *,
    required_skills: tuple[str, ...] = (),
    required_years: float | None = None,
    required_education_level: EducationLevel | None = None,
    required_project_count: int | None = None,
) -> WeightedCriterion:
    """Build a `WeightedCriterion` using `template`'s preset weight for `dimension`, so callers
    building a JRP from a template don't have to repeat the percentage table by hand."""
    return WeightedCriterion(
        dimension=dimension,
        weight=preset_weights(template)[dimension],
        curve=curve,
        required_skills=required_skills,
        required_years=required_years,
        required_education_level=required_education_level,
        required_project_count=required_project_count,
    )
