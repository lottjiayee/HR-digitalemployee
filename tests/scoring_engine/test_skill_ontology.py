"""Tests for skill-ontology-backed matching (FR-27, test.md T2.14)."""

from __future__ import annotations

import unicodedata

import pytest

from hr_digital_employee.scoring_engine.skill_ontology import (
    IdentitySkillOntology,
    SynonymMapSkillOntology,
)


def test_identity_ontology_matches_exact_case_and_whitespace_insensitive() -> None:
    ontology = IdentitySkillOntology()

    assert ontology.resolves_same_skill("Python", " python ") is True


def test_identity_ontology_is_insensitive_to_internal_whitespace_too() -> None:
    # Regression: .strip() alone only trims the ends, so "Team  Leadership" (doubled internal
    # space) was wrongly treated as different from "Team Leadership" despite the class's own
    # docstring claiming whitespace-insensitivity -- a plausible false-negative must-have
    # rejection for real, irregularly-spaced OCR/PDF-extracted resume text.
    ontology = IdentitySkillOntology()

    assert ontology.resolves_same_skill("Team  Leadership", "Team Leadership") is True


def test_identity_ontology_does_not_resolve_different_phrasings() -> None:
    ontology = IdentitySkillOntology()

    assert ontology.resolves_same_skill("led a team", "team leadership") is False


def test_identity_ontology_resolves_nfc_and_nfd_forms_of_the_same_skill() -> None:
    # Regression (round 6): a skill name typed in a JRP YAML (NFC -- precomposed accented
    # characters, the form any ordinary text editor saves) and the same skill extracted from a
    # resume in NFD (decomposed -- common output of certain PDF text extractors and macOS/HFS+
    # -authored documents) render identically but are different code-point sequences. Confirmed a
    # candidate who genuinely has the required accented skill failed the must-have gate and scored
    # zero on it, purely from this invisible text-encoding difference.
    nfc_form = "Développement Web"
    nfd_form = unicodedata.normalize("NFD", nfc_form)
    assert nfc_form != nfd_form  # sanity check: genuinely different code-point sequences

    ontology = IdentitySkillOntology()

    assert ontology.resolves_same_skill(nfc_form, nfd_form) is True


def test_identity_ontology_resolves_german_eszett_case_folding() -> None:
    # Regression: `.lower()` does not perform full Unicode case-folding, so German "STRASSE"
    # (the conventional all-caps form, e.g. a certificate title) and "straße" (its native-
    # orthography lowercase form) did not compare equal despite being the same word --
    # `str.casefold()` is what Python's own docs recommend specifically for caseless matching.
    ontology = IdentitySkillOntology()

    assert ontology.resolves_same_skill("STRASSENVERKEHR", "straßenverkehr") is True


def test_identity_ontology_resolves_a_ligature_to_its_plain_ascii_form() -> None:
    # Regression: a ligature glyph a PDF-embedded font substitutes (e.g. U+FB01 "ﬁ" in place of
    # "fi" -- common LaTeX/InDesign/Word-embedded-font output, directly relevant since this
    # system's own PDF pipeline uses pypdf) renders identically to its plain-ASCII form but is a
    # different code point; NFC alone (round 6's fix) only collapses canonical equivalents
    # (decomposed/precomposed accents), not compatibility equivalents like ligatures -- NFKC does.
    ontology = IdentitySkillOntology()

    plain = "Certified finance Professional"
    ligature = "Certified ﬁnance Professional"
    assert ontology.resolves_same_skill(plain, ligature) is True


def test_identity_ontology_resolves_full_width_latin_letters() -> None:
    # Regression: full-width Latin letters (a common CJK-input-method artifact) render
    # identically to their plain-ASCII form but are different code points, requiring NFKC's
    # compatibility folding (not just NFC) to match.
    ontology = IdentitySkillOntology()

    assert ontology.resolves_same_skill("Python", "Ｐｙｔｈｏｎ") is True


def test_t2_14_synonym_map_ontology_resolves_different_phrasings_to_the_same_skill() -> None:
    ontology = SynonymMapSkillOntology([("led a team", "team leadership")])

    assert ontology.resolves_same_skill("led a team", "team leadership") is True


def test_synonym_map_ontology_still_matches_terms_outside_any_group_exactly() -> None:
    ontology = SynonymMapSkillOntology([("led a team", "team leadership")])

    assert ontology.resolves_same_skill("Python", "Python") is True
    assert ontology.resolves_same_skill("Python", "SQL") is False


def test_synonym_map_ontology_rejects_a_group_that_overlaps_an_earlier_one() -> None:
    # Regression: a later group sharing a term with an earlier one used to silently overwrite
    # that term's mapping, breaking the earlier group's synonymy with no error at all --
    # building ("Java","JVM") then ("JavaScript","JS","JVM") used to make "Java"/"JVM" stop
    # resolving as the same skill, silently, the moment the second group was added.
    with pytest.raises(ValueError, match="already mapped"):
        SynonymMapSkillOntology([("Java", "JVM"), ("JavaScript", "JS", "JVM")])
