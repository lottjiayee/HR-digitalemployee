"""Tests for skill-ontology-backed matching (FR-27, test.md T2.14)."""

from __future__ import annotations

from hr_digital_employee.scoring_engine.skill_ontology import (
    IdentitySkillOntology,
    SynonymMapSkillOntology,
)


def test_identity_ontology_matches_exact_case_and_whitespace_insensitive() -> None:
    ontology = IdentitySkillOntology()

    assert ontology.resolves_same_skill("Python", " python ") is True


def test_identity_ontology_does_not_resolve_different_phrasings() -> None:
    ontology = IdentitySkillOntology()

    assert ontology.resolves_same_skill("led a team", "team leadership") is False


def test_t2_14_synonym_map_ontology_resolves_different_phrasings_to_the_same_skill() -> None:
    ontology = SynonymMapSkillOntology([("led a team", "team leadership")])

    assert ontology.resolves_same_skill("led a team", "team leadership") is True


def test_synonym_map_ontology_still_matches_terms_outside_any_group_exactly() -> None:
    ontology = SynonymMapSkillOntology([("led a team", "team leadership")])

    assert ontology.resolves_same_skill("Python", "Python") is True
    assert ontology.resolves_same_skill("Python", "SQL") is False
