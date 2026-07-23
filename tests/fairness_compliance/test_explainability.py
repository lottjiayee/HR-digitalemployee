"""Tests for explainability-on-request (FR-25, test.md T4.11)."""

from __future__ import annotations

from hr_digital_employee.fairness_compliance.explainability import explain_score
from hr_digital_employee.scoring_engine.engine import ScoringEngine
from hr_digital_employee.scoring_engine.models import (
    JRP,
    CandidateProfile,
    Dimension,
    EducationLevel,
    MatchingCurve,
    MustHaveCriterion,
    MustHaveKind,
    Score,
    Tier,
    WeightedCriterion,
    WeightTemplate,
)

_JRP = JRP(
    jrp_id="role-1",
    role_name="Backend Engineer",
    version=1,
    weight_template=WeightTemplate.GENERAL,
    must_have_criteria=(
        MustHaveCriterion(
            kind=MustHaveKind.REQUIRED_SKILL, label="Must know Python", required_skill="Python"
        ),
    ),
    weighted_criteria=(
        WeightedCriterion(
            dimension=Dimension.MANDATORY_SKILLS,
            weight=40.0,
            curve=MatchingCurve.LINEAR,
            required_skills=("Python", "SQL"),
        ),
        WeightedCriterion(
            dimension=Dimension.EXPERIENCE_TENURE,
            weight=30.0,
            curve=MatchingCurve.LINEAR,
            required_years=5.0,
        ),
        WeightedCriterion(
            dimension=Dimension.EDUCATIONAL_LEVEL,
            weight=15.0,
            curve=MatchingCurve.LINEAR,
            required_education_level=EducationLevel.BACHELOR,
        ),
        WeightedCriterion(
            dimension=Dimension.PROJECT_RELEVANCE,
            weight=15.0,
            curve=MatchingCurve.LINEAR,
            required_project_count=2,
        ),
    ),
)


def test_t4_11_explanation_is_derived_from_the_existing_score_only() -> None:
    profile = CandidateProfile(
        skills=("Python", "SQL"),
        years_of_experience=5.0,
        education_level=EducationLevel.BACHELOR,
        project_count=2,
    )
    score = ScoringEngine().score(profile, _JRP, parser_version="stub-0.1.0")

    explanation = explain_score(score, _JRP)

    assert "100.0" in explanation.summary
    assert len(explanation.dimension_explanations) == 4


def test_explanation_for_a_must_have_failure_names_the_reason_alongside_the_score() -> None:
    # SOP 2.2.2/2.2.4 (2026-07-22 revision): a failed must-have is noted alongside the full score,
    # not in place of it -- the candidate still sees the complete basis for their result.
    profile = CandidateProfile(
        skills=("SQL",),  # missing the must-have Python
        years_of_experience=5.0,
        education_level=EducationLevel.BACHELOR,
        project_count=2,
    )
    score = ScoringEngine().score(profile, _JRP, parser_version="stub-0.1.0")

    explanation = explain_score(score, _JRP)

    assert "Must know Python" in explanation.summary
    assert "80.0" in explanation.summary
    assert len(explanation.dimension_explanations) == 4


def test_summary_displays_two_decimals_not_one() -> None:
    # Regression (round 6): displaying total_score at 1 decimal reintroduced a bug already fixed
    # in cli.py -- engine.py rounds to 2 places, so 79.95 (correctly mid_match) would print as
    # "80.0" at 1 decimal, sitting right at the high_match boundary and reading like a
    # tier-classification error even though the tier label itself is correct.
    score = Score(
        jrp_id="role-1",
        jrp_version=1,
        scoring_engine_version="stub-0.1.0",
        parser_version="stub-0.1.0",
        total_score=79.95,
        tier=Tier.MID_MATCH,
        passed_must_have=True,
        failed_must_have_labels=(),
        breakdown=(),
    )

    explanation = explain_score(score, _JRP)

    assert "79.95" in explanation.summary
    assert "80.0/100" not in explanation.summary
