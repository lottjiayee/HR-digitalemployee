"""Tests for scoring_engine domain models: JRP weight validation (test.md T2.1-T2.2) and tier
classification (test.md T2.13)."""

from __future__ import annotations

import pytest

from hr_digital_employee.scoring_engine.models import (
    JRP,
    CandidateProfile,
    Dimension,
    EducationLevel,
    MatchingCurve,
    MustHaveCriterion,
    MustHaveKind,
    Tier,
    TierThresholds,
    WeightedCriterion,
    WeightTemplate,
    weight_guideline_warnings,
)


def _criterion(dimension: Dimension, weight: float) -> WeightedCriterion:
    if dimension is Dimension.MANDATORY_SKILLS:
        return WeightedCriterion(
            dimension=dimension, weight=weight, curve=MatchingCurve.LINEAR,
            required_skills=("Python",),
        )
    if dimension is Dimension.EXPERIENCE_TENURE:
        return WeightedCriterion(
            dimension=dimension, weight=weight, curve=MatchingCurve.LINEAR, required_years=5.0,
        )
    if dimension is Dimension.EDUCATIONAL_LEVEL:
        return WeightedCriterion(
            dimension=dimension, weight=weight, curve=MatchingCurve.LINEAR,
            required_education_level=EducationLevel.BACHELOR,
        )
    return WeightedCriterion(
        dimension=dimension, weight=weight, curve=MatchingCurve.LINEAR, required_project_count=2,
    )


def test_t2_1_jrp_rejects_weights_that_do_not_sum_to_100() -> None:
    with pytest.raises(ValueError, match="must sum to 100"):
        JRP(
            jrp_id="role-1",
            role_name="Senior Engineer",
            version=1,
            weight_template=WeightTemplate.SENIOR_TECHNICAL,
            weighted_criteria=(
                _criterion(Dimension.MANDATORY_SKILLS, 35.0),
                _criterion(Dimension.EXPERIENCE_TENURE, 35.0),
                _criterion(Dimension.EDUCATIONAL_LEVEL, 10.0),
                _criterion(Dimension.PROJECT_RELEVANCE, 19.0),  # sums to 99, not 100
            ),
        )


def test_t2_2_jrp_accepts_weights_summing_to_exactly_100() -> None:
    jrp = JRP(
        jrp_id="role-1",
        role_name="Senior Engineer",
        version=1,
        weight_template=WeightTemplate.SENIOR_TECHNICAL,
        weighted_criteria=(
            _criterion(Dimension.MANDATORY_SKILLS, 35.0),
            _criterion(Dimension.EXPERIENCE_TENURE, 35.0),
            _criterion(Dimension.EDUCATIONAL_LEVEL, 10.0),
            _criterion(Dimension.PROJECT_RELEVANCE, 20.0),
        ),
    )
    assert sum(c.weight for c in jrp.weighted_criteria) == 100.0


def test_jrp_rejects_a_dimension_appearing_more_than_once() -> None:
    with pytest.raises(ValueError, match="at most once"):
        JRP(
            jrp_id="role-1",
            role_name="Senior Engineer",
            version=1,
            weight_template=WeightTemplate.GENERAL,
            weighted_criteria=(
                _criterion(Dimension.MANDATORY_SKILLS, 50.0),
                _criterion(Dimension.MANDATORY_SKILLS, 50.0),
            ),
        )


def test_must_have_required_skill_criterion_needs_a_skill_set() -> None:
    with pytest.raises(ValueError, match="required_skill"):
        MustHaveCriterion(kind=MustHaveKind.REQUIRED_SKILL, label="Must know Python")


def test_must_have_minimum_years_criterion_needs_minimum_years_set() -> None:
    with pytest.raises(ValueError, match="minimum_years"):
        MustHaveCriterion(kind=MustHaveKind.MINIMUM_YEARS_EXPERIENCE, label="Must have 2+ years")


def test_must_have_criterion_rejects_a_none_label() -> None:
    # Regression (round 6): a blank JRP-editor grid cell round-trips to None via pandas, not an
    # empty string -- nothing validated `label` at all, so it was accepted as "valid" and later
    # crashed both cli.py and the dashboard (`"; ".join(...)` on a None) the moment any candidate
    # actually failed the criterion.
    with pytest.raises(ValueError, match="label"):
        MustHaveCriterion(
            kind=MustHaveKind.REQUIRED_SKILL, label=None, required_skill="Python"  # type: ignore[arg-type]
        )


def test_must_have_criterion_rejects_a_blank_or_whitespace_only_label() -> None:
    with pytest.raises(ValueError, match="label"):
        MustHaveCriterion(kind=MustHaveKind.REQUIRED_SKILL, label="   ", required_skill="Python")


@pytest.mark.parametrize(
    ("total_score", "expected_tier"),
    [
        (79.0, Tier.MID_MATCH),
        (80.0, Tier.HIGH_MATCH),
        (59.0, Tier.LOW_MATCH),
        (60.0, Tier.MID_MATCH),
    ],
)
def test_t2_13_default_tier_thresholds_land_on_the_correct_side_of_the_boundary(
    total_score: float, expected_tier: Tier
) -> None:
    assert TierThresholds().classify(total_score) is expected_tier


def test_tier_thresholds_reject_an_inverted_range() -> None:
    with pytest.raises(ValueError, match="thresholds"):
        TierThresholds(high_match_min=50.0, mid_match_min=60.0)


def test_candidate_profile_rejects_negative_years_of_experience() -> None:
    with pytest.raises(ValueError, match="years_of_experience"):
        CandidateProfile(
            skills=(), years_of_experience=-1.0, education_level=EducationLevel.NONE,
            project_count=0,
        )


def test_candidate_profile_rejects_negative_project_count() -> None:
    with pytest.raises(ValueError, match="project_count"):
        CandidateProfile(
            skills=(), years_of_experience=0.0, education_level=EducationLevel.NONE,
            project_count=-1,
        )


def test_candidate_profile_rejects_nan_years_of_experience() -> None:
    # Regression: `nan < 0` is False, so a NaN silently passed the old check and went on to
    # poison every curve/total-score computation downstream with no exception anywhere.
    with pytest.raises(ValueError, match="finite"):
        CandidateProfile(
            skills=(), years_of_experience=float("nan"), education_level=EducationLevel.NONE,
            project_count=0,
        )


def test_candidate_profile_rejects_infinite_years_of_experience() -> None:
    # Regression: `inf < 0` is also False (like `nan < 0`), so Infinity sailed past the same old
    # negativity-only check just as NaN did, inconsistent with the `math.isfinite` guards this
    # file already applies elsewhere (MustHaveCriterion.minimum_years, WeightedCriterion.
    # required_years/required_project_count) -- every curve function treats `inf` as an
    # automatic max score, so this would otherwise let a candidate silently max out a dimension
    # with no genuinely-extracted number backing it.
    with pytest.raises(ValueError, match="finite"):
        CandidateProfile(
            skills=(), years_of_experience=float("inf"), education_level=EducationLevel.NONE,
            project_count=0,
        )


def test_must_have_minimum_years_rejects_nan() -> None:
    # Regression (round 6): `nan < 0` is False, so a YAML typo like `minimum_years: .nan` sailed
    # past the old negativity-only check, then silently created a must-have gate no candidate
    # could ever pass (NaN comparisons are always false) -- with no config-load error.
    with pytest.raises(ValueError, match="finite"):
        MustHaveCriterion(
            kind=MustHaveKind.MINIMUM_YEARS_EXPERIENCE, label="x", minimum_years=float("nan")
        )


def test_must_have_minimum_years_rejects_infinity() -> None:
    # Regression (round 6): `inf > 0` is True, so a positivity-only check let `minimum_years: .inf`
    # through -- likewise a permanent, invisible, unwinnable must-have gate.
    with pytest.raises(ValueError, match="finite"):
        MustHaveCriterion(
            kind=MustHaveKind.MINIMUM_YEARS_EXPERIENCE, label="x", minimum_years=float("inf")
        )


def test_weighted_criterion_experience_tenure_rejects_infinite_required_years() -> None:
    # Regression (round 6): `inf > 0` is True, so `required_years: .inf` passed the old
    # positivity-only check -- confirmed this makes curve_score permanently 0.0 for any finite
    # candidate, with no config-load error despite the value being nonsensical.
    with pytest.raises(ValueError, match="finite"):
        WeightedCriterion(
            dimension=Dimension.EXPERIENCE_TENURE,
            weight=30.0,
            curve=MatchingCurve.LINEAR,
            required_years=float("inf"),
        )


def test_weighted_criterion_project_relevance_rejects_infinite_required_project_count() -> None:
    with pytest.raises(ValueError, match="finite"):
        WeightedCriterion(
            dimension=Dimension.PROJECT_RELEVANCE,
            weight=20.0,
            curve=MatchingCurve.LINEAR,
            required_project_count=float("inf"),
        )


def test_weighted_criterion_rejects_a_bool_weight() -> None:
    # Regression: a quoted/typo'd YAML boolean (`weight: true`) parses as Python's True, which a
    # bare `0.0 <= weight <= 100.0` range check silently accepts as 1.0 -- the same "parses fine,
    # wrong type" gap already closed elsewhere in this file (JRP.version, MustHaveCriterion.label).
    with pytest.raises(ValueError, match="weight"):
        WeightedCriterion(
            dimension=Dimension.MANDATORY_SKILLS,
            weight=True,  # type: ignore[arg-type]
            curve=MatchingCurve.LINEAR,
            required_skills=("Python",),
        )


def test_weighted_criterion_experience_tenure_rejects_a_bool_required_years() -> None:
    with pytest.raises(ValueError, match="finite"):
        WeightedCriterion(
            dimension=Dimension.EXPERIENCE_TENURE,
            weight=30.0,
            curve=MatchingCurve.LINEAR,
            required_years=True,  # type: ignore[arg-type]
        )


def test_weighted_criterion_project_relevance_rejects_a_bool_required_project_count() -> None:
    with pytest.raises(ValueError, match="finite"):
        WeightedCriterion(
            dimension=Dimension.PROJECT_RELEVANCE,
            weight=20.0,
            curve=MatchingCurve.LINEAR,
            required_project_count=True,  # type: ignore[arg-type]
        )


def test_jrp_rejects_a_non_int_version() -> None:
    # Regression (round 6): a quoted YAML scalar (`version: "1"`) parsed fine as a str -- nothing
    # validated its type, so it wasn't caught until JRPRepository.save()'s monotonicity check
    # crashed later with an uncaught TypeError comparing int to str.
    with pytest.raises(ValueError, match="version"):
        JRP(
            jrp_id="role-1",
            role_name="Senior Engineer",
            version="1",  # type: ignore[arg-type]
            weight_template=WeightTemplate.GENERAL,
            weighted_criteria=(_criterion(Dimension.MANDATORY_SKILLS, 100.0),),
        )


def test_weight_guideline_warnings_flags_educational_level_over_the_default() -> None:
    jrp = JRP(
        jrp_id="role-1",
        role_name="Graduate Analyst",
        version=1,
        weight_template=WeightTemplate.JUNIOR_GRADUATE,
        weighted_criteria=(
            _criterion(Dimension.MANDATORY_SKILLS, 45.0),
            _criterion(Dimension.EXPERIENCE_TENURE, 5.0),
            _criterion(Dimension.EDUCATIONAL_LEVEL, 30.0),  # over the 15% guideline default
            _criterion(Dimension.PROJECT_RELEVANCE, 20.0),
        ),
    )

    warnings = weight_guideline_warnings(jrp)

    assert len(warnings) == 1
    assert "30.0%" in warnings[0]


def test_weight_guideline_warnings_empty_when_within_the_default() -> None:
    jrp = JRP(
        jrp_id="role-1",
        role_name="Senior Engineer",
        version=1,
        weight_template=WeightTemplate.SENIOR_TECHNICAL,
        weighted_criteria=(
            _criterion(Dimension.MANDATORY_SKILLS, 35.0),
            _criterion(Dimension.EXPERIENCE_TENURE, 35.0),
            _criterion(Dimension.EDUCATIONAL_LEVEL, 10.0),
            _criterion(Dimension.PROJECT_RELEVANCE, 20.0),
        ),
    )

    assert weight_guideline_warnings(jrp) == ()
