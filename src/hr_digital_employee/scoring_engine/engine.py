"""The Scoring Engine (design.md §3.4, FR-9): a pure, deterministic function of a candidate
profile and a JRP. No LLM, agent, or raw-resume-text input exists anywhere in this module -- that
is what makes FR-9 ("LLM-assisted output never alters score/tier/gating") true by construction
rather than by policy.
"""

from __future__ import annotations

from hr_digital_employee.scoring_engine.curves import apply_curve
from hr_digital_employee.scoring_engine.models import (
    JRP,
    SCORING_ENGINE_VERSION,
    CandidateProfile,
    Dimension,
    DimensionResult,
    EducationLevel,
    MustHaveCriterion,
    MustHaveKind,
    Score,
    WeightedCriterion,
)
from hr_digital_employee.scoring_engine.skill_ontology import IdentitySkillOntology, SkillOntology


def _skills_ratio(
    profile: CandidateProfile, required_skills: tuple[str, ...], ontology: SkillOntology
) -> float:
    if not required_skills:
        return 1.0
    matched = sum(
        1
        for required in required_skills
        if any(ontology.resolves_same_skill(required, candidate) for candidate in profile.skills)
    )
    return matched / len(required_skills)


def _meets_must_have(
    profile: CandidateProfile, criterion: MustHaveCriterion, ontology: SkillOntology
) -> bool:
    if criterion.kind is MustHaveKind.REQUIRED_SKILL:
        assert criterion.required_skill is not None  # enforced by MustHaveCriterion.__post_init__
        return any(
            ontology.resolves_same_skill(criterion.required_skill, candidate)
            for candidate in profile.skills
        )
    if criterion.kind is MustHaveKind.MINIMUM_YEARS_EXPERIENCE:
        assert criterion.minimum_years is not None
        return profile.years_of_experience >= criterion.minimum_years
    raise AssertionError(f"unhandled must-have kind {criterion.kind!r}")


def _ratio_for(
    profile: CandidateProfile, criterion: WeightedCriterion, ontology: SkillOntology
) -> float:
    if criterion.dimension is Dimension.MANDATORY_SKILLS:
        return _skills_ratio(profile, criterion.required_skills, ontology)
    if criterion.dimension is Dimension.EXPERIENCE_TENURE:
        assert criterion.required_years is not None  # enforced by WeightedCriterion.__post_init__
        return profile.years_of_experience / criterion.required_years
    if criterion.dimension is Dimension.EDUCATIONAL_LEVEL:
        required_level = criterion.required_education_level
        assert required_level is not None
        if required_level is EducationLevel.NONE:
            return 1.0
        return profile.education_level / required_level
    if criterion.dimension is Dimension.PROJECT_RELEVANCE:
        assert criterion.required_project_count is not None
        return profile.project_count / criterion.required_project_count
    raise AssertionError(f"unhandled dimension {criterion.dimension!r}")


class ScoringEngine:
    """Scores one candidate profile against one JRP (design.md §3.4 sequence: must-have gate ->
    weighted dimension scoring -> normalize -> tier classification)."""

    def __init__(
        self,
        skill_ontology: SkillOntology | None = None,
        engine_version: str = SCORING_ENGINE_VERSION,
    ) -> None:
        self._skill_ontology = skill_ontology or IdentitySkillOntology()
        self._engine_version = engine_version

    def score(self, profile: CandidateProfile, jrp: JRP, parser_version: str) -> Score:
        """`parser_version` identifies the Module 1 extraction run `profile` was derived from
        (NFR-5: every score records both the scoring-engine and the parser version).

        A failed must-have criterion no longer withholds the weighted score (SOP 2.2.2/2.2.4,
        2026-07-22 revision): it is flagged alongside a fully-computed score/breakdown so HR sees
        the whole profile before deciding, rather than an opaque 0/Low-Match with no detail. Every
        failing must-have is recorded, not just the first -- a candidate missing three must-haves
        is entitled to see all three, not one arbitrary pick."""
        failed_labels = tuple(
            criterion.label
            for criterion in jrp.must_have_criteria
            if not _meets_must_have(profile, criterion, self._skill_ontology)
        )

        breakdown: list[DimensionResult] = []
        total_score = 0.0
        for weighted_criterion in jrp.weighted_criteria:
            raw_ratio = _ratio_for(profile, weighted_criterion, self._skill_ontology)
            curve_score = apply_curve(weighted_criterion.curve, raw_ratio)
            contribution = curve_score * weighted_criterion.weight
            total_score += contribution
            breakdown.append(
                DimensionResult(
                    dimension=weighted_criterion.dimension,
                    raw_ratio=raw_ratio,
                    curve_score=curve_score,
                    weight=weighted_criterion.weight,
                    contribution=contribution,
                )
            )

        total_score = round(total_score, 2)
        return Score(
            jrp_id=jrp.jrp_id,
            jrp_version=jrp.version,
            scoring_engine_version=self._engine_version,
            parser_version=parser_version,
            total_score=total_score,
            tier=jrp.tier_thresholds.classify(total_score),
            passed_must_have=not failed_labels,
            failed_must_have_labels=failed_labels,
            breakdown=tuple(breakdown),
        )
