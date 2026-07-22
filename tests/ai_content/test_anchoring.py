"""Tests for sentence-to-source anchoring (FR-10, test.md T3.1-T3.2)."""

from __future__ import annotations

from hr_digital_employee.ai_content.anchoring import anchor_for, anchor_sentences
from hr_digital_employee.ai_content.models import SourcePassage

PASSAGES = (
    SourcePassage(field_name="skills", text="Python, SQL"),
    SourcePassage(field_name="education", text="Bachelor of Computer Science"),
)


def test_t3_1_a_sentence_grounded_in_a_passage_is_anchored() -> None:
    field = anchor_for("The candidate lists the following skills: Python, SQL.", PASSAGES)

    assert field == "skills"


def test_t3_2_a_fabricated_sentence_with_no_source_is_not_anchored() -> None:
    field = anchor_for("The candidate won a national chess championship in 2015.", PASSAGES)

    assert field is None


def test_anchor_sentences_drops_unanchored_sentences_and_keeps_anchored_ones() -> None:
    sentences = (
        "The candidate lists the following skills: Python, SQL.",
        "The candidate won a national chess championship in 2015.",  # fabricated, no source
        "Education: Bachelor of Computer Science.",
    )

    anchored = anchor_sentences(sentences, PASSAGES)

    assert len(anchored) == 2
    assert [a.source_field for a in anchored] == ["skills", "education"]


def test_anchor_for_returns_none_when_no_passages_are_available() -> None:
    assert anchor_for("Anything at all.", ()) is None
