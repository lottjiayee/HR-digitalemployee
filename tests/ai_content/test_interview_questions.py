"""Tests for interview question generation (FR-12, test.md T3.3)."""

from __future__ import annotations

from hr_digital_employee.ai_content.interview_questions import generate_interview_questions
from hr_digital_employee.ai_content.models import QuestionAngle
from hr_digital_employee.intake_extraction.extraction import ExtractionService
from hr_digital_employee.scoring_engine.engine import ScoringEngine
from hr_digital_employee.scoring_engine.models import (
    JRP,
    Dimension,
    DimensionResult,
    EducationLevel,
    MatchingCurve,
    Score,
    Tier,
    WeightedCriterion,
    WeightTemplate,
)
from hr_digital_employee.scoring_engine.profile_adapter import build_candidate_profile

_JRP = JRP(
    jrp_id="role-1",
    role_name="Backend Engineer",
    version=1,
    weight_template=WeightTemplate.GENERAL,
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
            required_years=10.0,
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


def test_t3_3_questions_cover_verification_gap_and_behavioral_angles() -> None:
    resume_text = (
        "Skills:\nPython\nSQL\n\n"
        "Projects:\nBuilt a data pipeline\n\n"
        "Working Experience:\n2 years at TechCorp\n\n"  # well below the 10-year requirement
        "Education:\nBachelor of Computer Science\n"
    )
    extracted = ExtractionService().extract(resume_text)
    profile = build_candidate_profile(extracted)
    score = ScoringEngine().score(profile, _JRP, extracted.parser_version)

    questions = generate_interview_questions(score, extracted)

    angles = {q.angle for q in questions}
    assert QuestionAngle.VERIFICATION in angles  # Mandatory Skills: 2/2, strong
    assert QuestionAngle.GAP in angles  # Experience Tenure: 2/10, weak
    assert QuestionAngle.BEHAVIORAL in angles  # always included


def test_all_three_angles_are_covered_even_when_every_dimension_is_mid_range() -> None:
    # Regression test: every dimension scoring in the (LOW_SCORE_THRESHOLD, HIGH_SCORE_THRESHOLD)
    # "dead zone" used to produce zero VERIFICATION and zero GAP questions -- a real risk since
    # that band covers the entire Mid Match tier (60-79%), not a rare edge case. Uses a dedicated
    # JRP tuned so every dimension's ratio lands strictly inside (0.5, 0.85), which two required
    # skills alone can't produce (0/2, 1/2, 2/2 only) -- hence the wider requirements here.
    mid_range_jrp = JRP(
        jrp_id="role-2",
        role_name="Backend Engineer",
        version=1,
        weight_template=WeightTemplate.GENERAL,
        weighted_criteria=(
            WeightedCriterion(
                dimension=Dimension.MANDATORY_SKILLS,
                weight=40.0,
                curve=MatchingCurve.LINEAR,
                required_skills=("Python", "SQL", "JavaScript"),  # candidate has 2/3 -> 0.667
            ),
            WeightedCriterion(
                dimension=Dimension.EXPERIENCE_TENURE,
                weight=30.0,
                curve=MatchingCurve.LINEAR,
                required_years=10.0,  # candidate has 7 -> 0.7
            ),
            WeightedCriterion(
                dimension=Dimension.EDUCATIONAL_LEVEL,
                weight=15.0,
                curve=MatchingCurve.LINEAR,
                required_education_level=EducationLevel.MASTER,  # candidate has Bachelor -> 0.75
            ),
            WeightedCriterion(
                dimension=Dimension.PROJECT_RELEVANCE,
                weight=15.0,
                curve=MatchingCurve.LINEAR,
                required_project_count=3,  # candidate has 2 -> 0.667
            ),
        ),
    )
    resume_text = (
        "Skills:\nPython\nSQL\n\n"
        "Projects:\nBuilt a data pipeline\nLed a small team\n\n"
        "Working Experience:\n7 years at TechCorp\n\n"
        "Education:\nBachelor of Computer Science\n"
    )
    extracted = ExtractionService().extract(resume_text)
    profile = build_candidate_profile(extracted)
    score = ScoringEngine().score(profile, mid_range_jrp, extracted.parser_version)

    # Confirm the premise: nothing crosses either threshold on its own.
    assert all(0.5 < r.curve_score < 0.85 for r in score.breakdown)

    questions = generate_interview_questions(score, extracted)

    angles = [q.angle for q in questions]
    assert QuestionAngle.VERIFICATION in angles
    assert QuestionAngle.GAP in angles
    assert QuestionAngle.BEHAVIORAL in angles


def test_no_contradictory_questions_when_every_dimension_is_a_strength() -> None:
    # Regression: when every dimension already cleared HIGH_SCORE_THRESHOLD (and so already got
    # its own verification question), the gap-fallback used to still pick the *weakest of the
    # strengths* and ask a gap question about it too -- e.g. "you scored strongly on your project
    # work" and, about that same dimension, "your profile shows your project work below this
    # role's target" in the same output.
    strong_jrp = JRP(
        jrp_id="role-3",
        role_name="Backend Engineer",
        version=1,
        weight_template=WeightTemplate.GENERAL,
        weighted_criteria=(
            WeightedCriterion(
                dimension=Dimension.MANDATORY_SKILLS,
                weight=40.0,
                curve=MatchingCurve.LINEAR,
                required_skills=("Python",),
            ),
            WeightedCriterion(
                dimension=Dimension.EXPERIENCE_TENURE,
                weight=30.0,
                curve=MatchingCurve.LINEAR,
                required_years=1.0,
            ),
            WeightedCriterion(
                dimension=Dimension.EDUCATIONAL_LEVEL,
                weight=15.0,
                curve=MatchingCurve.LINEAR,
                required_education_level=EducationLevel.HIGH_SCHOOL,
            ),
            WeightedCriterion(
                dimension=Dimension.PROJECT_RELEVANCE,
                weight=15.0,
                curve=MatchingCurve.LINEAR,
                required_project_count=1,
            ),
        ),
    )
    resume_text = (
        "Skills:\nPython\n\n"
        "Projects:\nBuilt a data pipeline\n\n"
        "Working Experience:\n10 years at TechCorp\n\n"
        "Education:\nBachelor of Computer Science\n"
    )
    extracted = ExtractionService().extract(resume_text)
    profile = build_candidate_profile(extracted)
    score = ScoringEngine().score(profile, strong_jrp, extracted.parser_version)
    assert all(r.curve_score >= 0.85 for r in score.breakdown)  # confirm the premise

    questions = generate_interview_questions(score, extracted)

    assert not any(q.angle is QuestionAngle.GAP for q in questions)
    assert sum(1 for q in questions if q.angle is QuestionAngle.VERIFICATION) == 4


def _score_with_breakdown(breakdown: tuple[DimensionResult, ...]) -> Score:
    return Score(
        jrp_id="role-x",
        jrp_version=1,
        scoring_engine_version="stub-0.1.0",
        parser_version="stub-0.1.0",
        total_score=70.0,
        tier=Tier.MID_MATCH,
        passed_must_have=True,
        failed_must_have_labels=(),
        breakdown=breakdown,
    )


def test_a_single_mid_range_dimension_gets_only_one_fallback_question_not_both() -> None:
    # Regression (round 6): with only one dimension in the breakdown, max()/min() both resolve to
    # that same dimension -- the old fallback asked both a verification question ("you scored
    # strongly") and a gap question ("shows a gap") about the identical dimension in the same
    # output, exactly the self-contradiction the surrounding code comment says should be
    # impossible.
    score = _score_with_breakdown(
        (DimensionResult(Dimension.MANDATORY_SKILLS, 0.7, 0.7, 100.0, 70.0),)
    )
    extracted = ExtractionService().extract("Skills:\nPython\n")

    questions = generate_interview_questions(score, extracted)

    verification_dims = {
        q.text for q in questions if q.angle is QuestionAngle.VERIFICATION
    }
    gap_dims = {q.text for q in questions if q.angle is QuestionAngle.GAP}
    assert not (verification_dims and gap_dims)  # never both angles about the sole dimension


def test_two_dimensions_tied_at_the_same_mid_range_score_each_get_their_own_question() -> None:
    # Regression (round 6): when every dimension ties at the identical mid-range score, max() and
    # min() both resolve to the *first* tied element -- the second, equally mid-range dimension
    # silently got no fallback question at all.
    score = _score_with_breakdown(
        (
            DimensionResult(Dimension.MANDATORY_SKILLS, 0.7, 0.7, 50.0, 35.0),
            DimensionResult(Dimension.EXPERIENCE_TENURE, 0.7, 0.7, 50.0, 35.0),
        )
    )
    extracted = ExtractionService().extract("Skills:\nPython\n")

    questions = generate_interview_questions(score, extracted)

    assert any(q.angle is QuestionAngle.VERIFICATION for q in questions)
    assert any(q.angle is QuestionAngle.GAP for q in questions)
    verification_text = next(q.text for q in questions if q.angle is QuestionAngle.VERIFICATION)
    gap_text = next(q.text for q in questions if q.angle is QuestionAngle.GAP)
    assert verification_text != gap_text  # two distinct dimensions, not the same one twice


def test_a_mid_range_fallback_question_does_not_overclaim_strength_or_a_gap() -> None:
    # Regression: the fallback for an all-mid-range candidate reused _verification_question/
    # _gap_question's "you scored strongly"/"below this role's target" wording -- confirmed a
    # candidate scoring 55%/52% (a LOW_MATCH-tier candidate) was told they "scored strongly" on
    # one dimension purely because it was this candidate's least-bad dimension, and that the other
    # was "below target" purely because it was the worst -- misleading interview prep for a
    # dimension that never actually crossed HIGH_SCORE_THRESHOLD/LOW_SCORE_THRESHOLD at all. The
    # fallback must use explicitly relative wording instead.
    score = _score_with_breakdown(
        (
            DimensionResult(Dimension.MANDATORY_SKILLS, 0.55, 0.55, 50.0, 27.5),
            DimensionResult(Dimension.EXPERIENCE_TENURE, 0.52, 0.52, 50.0, 26.0),
        )
    )
    extracted = ExtractionService().extract("Skills:\nPython\n")

    questions = generate_interview_questions(score, extracted)

    verification_text = next(q.text for q in questions if q.angle is QuestionAngle.VERIFICATION)
    gap_text = next(q.text for q in questions if q.angle is QuestionAngle.GAP)
    assert "scored strongly" not in verification_text
    assert "relatively strongest" in verification_text
    assert "below this role's target" not in gap_text
    assert "relatively weakest" in gap_text


def test_behavioral_question_references_a_real_project_when_available() -> None:
    resume_text = "Skills:\nPython\n\nProjects:\nBuilt an internal analytics dashboard\n"
    extracted = ExtractionService().extract(resume_text)
    profile = build_candidate_profile(extracted)
    score = ScoringEngine().score(profile, _JRP, extracted.parser_version)

    questions = generate_interview_questions(score, extracted)

    behavioral = next(q for q in questions if q.angle is QuestionAngle.BEHAVIORAL)
    assert "Built an internal analytics dashboard" in behavioral.text
