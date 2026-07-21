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


def test_t2_3_candidate_failing_must_have_is_forced_to_low_match_with_no_weighted_score() -> None:
    profile = CandidateProfile(
        skills=("SQL",),  # missing the must-have "Python"
        years_of_experience=8.0,
        education_level=EducationLevel.MASTER,
        project_count=5,
    )

    score = ScoringEngine().score(profile, _GENERAL_JRP, parser_version="stub-0.1.0")

    assert score.passed_must_have is False
    assert score.failed_must_have_label == "Must know Python"
    assert score.tier is Tier.LOW_MATCH
    assert score.total_score == 0.0
    assert score.breakdown == ()


def test_t2_4_candidate_passing_must_have_but_scoring_poorly_gets_a_normal_weighted_score() -> None:
    profile = CandidateProfile(
        skills=("Python",),  # must-have met, but weak on everything else weighted
        years_of_experience=1.0,
        education_level=EducationLevel.HIGH_SCHOOL,
        project_count=0,
    )

    score = ScoringEngine().score(profile, _GENERAL_JRP, parser_version="stub-0.1.0")

    assert score.passed_must_have is True
    assert score.failed_must_have_label is None
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
