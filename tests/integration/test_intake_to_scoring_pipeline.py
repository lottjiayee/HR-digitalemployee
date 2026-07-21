"""End-to-end test: a resume submission goes in through the Ingestion Gateway (Module 1) and a
Score comes out through the Scoring Engine (Module 2), via the profile adapter connecting them.

This is the thing unit tests within each module can't prove on their own: that Module 2 can
actually score a resume Module 1 really extracted, not just a hand-built `CandidateProfile` fixture.
"""

from __future__ import annotations

from datetime import UTC, datetime

from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog
from hr_digital_employee.intake_extraction.dedup import IdentityDedupService
from hr_digital_employee.intake_extraction.extraction import ExtractionService
from hr_digital_employee.intake_extraction.gateway import IngestionGateway
from hr_digital_employee.intake_extraction.manual_review_queue import ManualReviewQueue
from hr_digital_employee.intake_extraction.models import RawSubmission, SubmissionChannel
from hr_digital_employee.scoring_engine.engine import ScoringEngine
from hr_digital_employee.scoring_engine.models import (
    JRP,
    Dimension,
    EducationLevel,
    MatchingCurve,
    MustHaveCriterion,
    MustHaveKind,
    Tier,
    WeightedCriterion,
    WeightTemplate,
)
from hr_digital_employee.scoring_engine.profile_adapter import build_candidate_profile

RESUME_TEXT = (
    b"Skills:\nPython\nSQL\n\n"
    b"Projects:\nBuilt a data pipeline\nLed a small team\n\n"
    b"Working Experience:\n5 years at TechCorp as a backend engineer\n\n"
    b"Education:\nBachelor of Computer Science\n"
)


class _StaticChannelAdapter:
    def __init__(self, submissions: list[RawSubmission]) -> None:
        self._submissions = submissions

    def fetch_new_submissions(self) -> list[RawSubmission]:
        return self._submissions


def _backend_engineer_jrp() -> JRP:
    return JRP(
        jrp_id="backend-engineer",
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
                curve=MatchingCurve.BUFFERED,
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


def test_a_real_resume_flows_from_intake_through_to_a_score() -> None:
    submission = RawSubmission(
        channel=SubmissionChannel.EMAIL,
        candidate_email="jane@example.com",
        candidate_phone=None,
        candidate_name="Jane Doe",
        file_bytes=RESUME_TEXT,
        received_at=datetime.now(UTC),
    )
    gateway = IngestionGateway(
        channel_adapters=[_StaticChannelAdapter([submission])],
        extraction_service=ExtractionService(),
        dedup_service=IdentityDedupService(),
        manual_review_queue=ManualReviewQueue(),
        audit_log=InMemoryAuditLog(),
    )

    results = gateway.run_once()
    assert len(results) == 1
    candidate, extracted = results[0]

    profile = build_candidate_profile(extracted)
    score = ScoringEngine().score(profile, _backend_engineer_jrp(), extracted.parser_version)

    assert candidate.email == "jane@example.com"
    assert score.passed_must_have is True
    assert score.parser_version == extracted.parser_version
    # Python+SQL 2/2, 5/5 years, Bachelor meets Bachelor, 2/2 projects -> everything maxes out.
    assert score.total_score == 100.0
    assert score.tier is Tier.HIGH_MATCH
