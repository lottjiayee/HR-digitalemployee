"""Tests for skill-ontology maintenance (FR-27, test.md T4.13)."""

from __future__ import annotations

import pytest

from hr_digital_employee.fairness_compliance.skill_ontology_store import SkillOntologyRepository
from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog
from hr_digital_employee.scoring_engine.engine import ScoringEngine
from hr_digital_employee.scoring_engine.models import (
    JRP,
    CandidateProfile,
    Dimension,
    EducationLevel,
    MatchingCurve,
    WeightedCriterion,
    WeightTemplate,
)


def test_synonym_group_resolves_different_phrasings_as_the_same_skill() -> None:
    repo = SkillOntologyRepository(InMemoryAuditLog())
    repo.add_synonym_group(
        ("team leadership", "led a team"), actor="hr_alice", reason="observed phrasing variance"
    )

    assert repo.resolves_same_skill("led a team", "team leadership") is True


def test_terms_outside_any_group_still_match_exactly() -> None:
    repo = SkillOntologyRepository(InMemoryAuditLog())
    repo.add_synonym_group(("team leadership", "led a team"), actor="hr_alice", reason="test")

    assert repo.resolves_same_skill("Python", "Python") is True
    assert repo.resolves_same_skill("Python", "SQL") is False


def test_a_group_overlapping_an_earlier_ones_term_is_rejected_not_silently_applied() -> None:
    # Regression: a later group sharing a term with an earlier one used to silently overwrite
    # that term's mapping, breaking the earlier group's synonymy with no error -- a routine
    # ontology edit could silently make a JD requiring "C#" stop matching a candidate who listed
    # "CSharp", with zero visibility into why.
    repo = SkillOntologyRepository(InMemoryAuditLog())
    repo.add_synonym_group(("C#", "CSharp"), actor="hr_alice", reason="initial group")

    with pytest.raises(ValueError, match="already mapped"):
        repo.add_synonym_group(("C", "C#"), actor="hr_alice", reason="overlapping group")

    assert repo.resolves_same_skill("C#", "CSharp") is True  # unchanged by the rejected update


def test_updates_are_audit_logged() -> None:
    audit_log = InMemoryAuditLog()
    repo = SkillOntologyRepository(audit_log)

    repo.add_synonym_group(("team leadership", "led a team"), actor="hr_alice", reason="test")

    events = audit_log.events_for("skill-ontology")
    assert len(events) == 1
    assert events[0].action == "synonym_group_added"
    assert events[0].actor == "hr_alice"


def test_t4_13_repository_satisfies_the_scoring_engines_skill_ontology_protocol_structurally() -> (
    None
):
    # No import of scoring_engine anywhere in fairness_compliance -- this proves
    # SkillOntologyRepository is still a drop-in for ScoringEngine's skill_ontology parameter via
    # structural typing alone (see skill_ontology_store.py's module docstring).
    repo = SkillOntologyRepository(InMemoryAuditLog())
    repo.add_synonym_group(("Python", "python programming"), actor="hr_alice", reason="test")

    jrp = JRP(
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
                required_years=1.0,
            ),
            WeightedCriterion(
                dimension=Dimension.EDUCATIONAL_LEVEL,
                weight=15.0,
                curve=MatchingCurve.LINEAR,
                required_education_level=EducationLevel.NONE,
            ),
            WeightedCriterion(
                dimension=Dimension.PROJECT_RELEVANCE,
                weight=15.0,
                curve=MatchingCurve.LINEAR,
                required_project_count=1,
            ),
        ),
    )
    profile = CandidateProfile(
        skills=("python programming",),  # differently-phrased, resolved via the ontology
        years_of_experience=1.0,
        education_level=EducationLevel.NONE,
        project_count=1,
    )

    score = ScoringEngine(skill_ontology=repo).score(profile, jrp, parser_version="stub-0.1.0")

    assert score.total_score == 100.0
