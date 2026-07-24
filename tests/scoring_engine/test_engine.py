"""Integration tests for the Scoring Engine (test.md §2)."""

from __future__ import annotations

from hr_digital_employee.scoring_engine.engine import ScoringEngine
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
)
from hr_digital_employee.scoring_engine.skill_ontology import SynonymMapSkillOntology

_GENERAL_JRP = JRP(
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


def test_t2_3_candidate_failing_must_have_is_flagged_alongside_a_full_weighted_score() -> None:
    # SOP 2.2.2/2.2.4 (2026-07-22 revision): a failed must-have no longer withholds the score --
    # it's flagged alongside a fully-computed score/breakdown so HR sees the whole profile.
    profile = CandidateProfile(
        skills=("SQL",),  # missing the must-have "Python"
        years_of_experience=8.0,
        education_level=EducationLevel.MASTER,
        project_count=5,
    )

    score = ScoringEngine().score(profile, _GENERAL_JRP, parser_version="stub-0.1.0")

    assert score.passed_must_have is False
    assert score.failed_must_have_labels == ("Must know Python",)
    assert score.total_score == 80.0
    assert len(score.breakdown) == 4


def test_a_candidate_failing_multiple_must_haves_has_every_one_named_not_just_the_first() -> None:
    # Regression: `failed_must_have_label` (singular) only ever surfaced the FIRST failing
    # must-have, silently hiding the rest -- directly contradicting the 2026-07-22 SOP revision's
    # own stated purpose of showing HR the full profile before deciding.
    jrp = JRP(
        jrp_id="role-2",
        role_name="Platform Engineer",
        version=1,
        weight_template=WeightTemplate.GENERAL,
        must_have_criteria=(
            MustHaveCriterion(
                kind=MustHaveKind.REQUIRED_SKILL, label="Must know Python", required_skill="Python"
            ),
            MustHaveCriterion(
                kind=MustHaveKind.REQUIRED_SKILL,
                label="Must know Kubernetes",
                required_skill="Kubernetes",
            ),
            MustHaveCriterion(
                kind=MustHaveKind.MINIMUM_YEARS_EXPERIENCE,
                label="Must have 10+ years",
                minimum_years=10.0,
            ),
        ),
        weighted_criteria=_GENERAL_JRP.weighted_criteria,
    )
    profile = CandidateProfile(
        skills=("SQL",),  # meets neither Python nor Kubernetes
        years_of_experience=1.0,  # meets neither the years floor
        education_level=EducationLevel.BACHELOR,
        project_count=0,
    )

    score = ScoringEngine().score(profile, jrp, parser_version="stub-0.1.0")

    assert score.passed_must_have is False
    assert score.failed_must_have_labels == (
        "Must know Python",
        "Must know Kubernetes",
        "Must have 10+ years",
    )


def test_t2_4_candidate_passing_must_have_but_scoring_poorly_gets_a_normal_weighted_score() -> None:
    profile = CandidateProfile(
        skills=("Python",),  # must-have met, but weak on everything else weighted
        years_of_experience=1.0,
        education_level=EducationLevel.HIGH_SCHOOL,
        project_count=0,
    )

    score = ScoringEngine().score(profile, _GENERAL_JRP, parser_version="stub-0.1.0")

    assert score.passed_must_have is True
    assert score.failed_must_have_labels == ()
    assert score.total_score > 0.0
    assert len(score.breakdown) == 4


def test_full_scoring_matches_hand_calculated_total() -> None:
    profile = CandidateProfile(
        skills=("Python", "SQL"),  # 2/2 -> 100% on Mandatory Skills (weight 40)
        years_of_experience=5.0,  # 5/5 -> 100% on Experience Tenure (weight 30)
        education_level=EducationLevel.BACHELOR,  # 3/3 -> 100% on Educational Level (weight 15)
        project_count=1,  # 1/2 -> 50% on Project Relevance (weight 15)
    )

    score = ScoringEngine().score(profile, _GENERAL_JRP, parser_version="stub-0.1.0")

    # 40*1.0 + 30*1.0 + 15*1.0 + 15*0.5 = 92.5
    assert score.total_score == 92.5
    assert score.tier is Tier.HIGH_MATCH
    assert score.parser_version == "stub-0.1.0"  # NFR-5: parser version, not just engine version


def test_a_maxed_out_candidate_scores_exactly_100_even_when_weights_sum_to_99_99() -> None:
    # Regression: JRP.__post_init__ accepts any weight sum within 0.01 of 100 (legitimate rounding
    # slop, e.g. splitting a JRP's weight evenly three ways -- 33.33 x 3 = 99.99). Before this fix,
    # total_score was the raw weighted sum, so a JRP whose weights summed to 99.99 could never
    # score higher than 99.99 -- permanently below a `high_match_min` of 100.0. A candidate who
    # maxes every single dimension (curve_score == 1.0 throughout) is the best possible candidate
    # this JRP can describe and must reach the top tier, not be misclassified as Mid Match purely
    # from the weight-sum's rounding slop.
    jrp = JRP(
        jrp_id="role-slop",
        role_name="Backend Engineer",
        version=1,
        weight_template=WeightTemplate.GENERAL,
        weighted_criteria=(
            WeightedCriterion(
                dimension=Dimension.MANDATORY_SKILLS,
                weight=39.99,
                curve=MatchingCurve.LINEAR,
                required_skills=("Python",),
            ),
            WeightedCriterion(
                dimension=Dimension.EXPERIENCE_TENURE,
                weight=30.0,
                curve=MatchingCurve.LINEAR,
                required_years=2.0,
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
        tier_thresholds=TierThresholds(high_match_min=100.0, mid_match_min=60.0),
    )
    profile = CandidateProfile(
        skills=("Python",),
        years_of_experience=10.0,
        education_level=EducationLevel.DOCTORATE,
        project_count=10,
    )

    score = ScoringEngine().score(profile, jrp, parser_version="stub-0.1.0")

    assert score.total_score == 100.0
    assert score.tier is Tier.HIGH_MATCH


def test_scoring_is_deterministic_for_identical_inputs() -> None:
    profile = CandidateProfile(
        skills=("Python", "SQL"),
        years_of_experience=6.0,
        education_level=EducationLevel.MASTER,
        project_count=3,
    )
    engine = ScoringEngine()

    first = engine.score(profile, _GENERAL_JRP, parser_version="stub-0.1.0")
    second = engine.score(profile, _GENERAL_JRP, parser_version="stub-0.1.0")

    assert first == second


def test_scoring_engine_version_is_stamped_on_the_score() -> None:
    profile = CandidateProfile(
        skills=("Python", "SQL"),
        years_of_experience=6.0,
        education_level=EducationLevel.MASTER,
        project_count=3,
    )

    old_version_score = ScoringEngine(engine_version="stub-0.1.0").score(
        profile, _GENERAL_JRP, parser_version="stub-0.1.0"
    )
    new_version_score = ScoringEngine(engine_version="stub-0.2.0").score(
        profile, _GENERAL_JRP, parser_version="stub-0.1.0"
    )

    assert old_version_score.scoring_engine_version == "stub-0.1.0"
    assert new_version_score.scoring_engine_version == "stub-0.2.0"
    # NFR-5: upgrading the engine version produces a new Score, the original is untouched.
    assert old_version_score != new_version_score


def test_skill_ontology_resolves_different_phrasings_during_scoring() -> None:
    ontology = SynonymMapSkillOntology([("Python", "python programming")])
    jrp = JRP(
        jrp_id="role-2",
        role_name="Backend Engineer",
        version=1,
        weight_template=WeightTemplate.GENERAL,
        weighted_criteria=(
            WeightedCriterion(
                dimension=Dimension.MANDATORY_SKILLS,
                weight=100.0,
                curve=MatchingCurve.LINEAR,
                required_skills=("Python",),
            ),
        ),
    )
    profile = CandidateProfile(
        skills=("python programming",),
        years_of_experience=0.0,
        education_level=EducationLevel.NONE,
        project_count=0,
    )

    score = ScoringEngine(skill_ontology=ontology).score(profile, jrp, parser_version="stub-0.1.0")

    assert score.total_score == 100.0
