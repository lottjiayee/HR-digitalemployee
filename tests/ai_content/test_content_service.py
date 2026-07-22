"""Integration tests for ContentGenerationService, tying summary/questions/flags together."""

from __future__ import annotations

from hr_digital_employee.ai_content.content_service import ContentGenerationService
from hr_digital_employee.ai_content.hallucination_audit import HallucinationAuditLog
from hr_digital_employee.intake_extraction.extraction import ExtractionService
from hr_digital_employee.scoring_engine.engine import ScoringEngine
from hr_digital_employee.scoring_engine.models import (
    JRP,
    Dimension,
    EducationLevel,
    MatchingCurve,
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
            required_skills=("Python",),
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
            required_project_count=1,
        ),
    ),
)

RESUME_TEXT = (
    "Skills:\nPython\nSQL\n\n"
    "Projects:\nBuilt a data pipeline\n\n"
    "Working Experience:\n5 years at TechCorp as a backend engineer\n\n"
    "Education:\nBachelor of Computer Science\n"
)


def test_generate_returns_summary_questions_and_flags_together() -> None:
    extracted = ExtractionService().extract(RESUME_TEXT)
    profile = build_candidate_profile(extracted)
    score = ScoringEngine().score(profile, _JRP, extracted.parser_version)

    content = ContentGenerationService().generate("cand-1", extracted, score)

    assert len(content.summary.sentences) > 0
    assert len(content.interview_questions) > 0
    assert content.red_flags == ()  # clean, consistent resume


def test_generate_records_to_the_hallucination_audit_log_when_provided() -> None:
    extracted = ExtractionService().extract(RESUME_TEXT)
    profile = build_candidate_profile(extracted)
    score = ScoringEngine().score(profile, _JRP, extracted.parser_version)
    audit_log = HallucinationAuditLog()

    ContentGenerationService(audit_log=audit_log).generate("cand-1", extracted, score)

    assert len(audit_log) == 1


def test_generate_does_not_require_an_audit_log() -> None:
    extracted = ExtractionService().extract(RESUME_TEXT)
    profile = build_candidate_profile(extracted)
    score = ScoringEngine().score(profile, _JRP, extracted.parser_version)

    content = ContentGenerationService().generate("cand-1", extracted, score)

    assert content is not None
