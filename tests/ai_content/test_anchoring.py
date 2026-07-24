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


def test_a_passage_made_entirely_of_short_technical_tokens_can_still_be_anchored() -> None:
    # Regression (round 6): a passage whose entire content is short tokens (e.g. skills "Go",
    # "R", "C" -- all under the 3-character significance bar) had zero significant tokens and
    # could never be matched, silently dropping a candidate's genuine, verbatim skills sentence
    # from the summary as if it were fabricated, even though there was zero hallucination risk.
    passages = (SourcePassage(field_name="skills", text="Go, R, C"),)

    field = anchor_for("The candidate lists the following skills: Go, R, C.", passages)

    assert field == "skills"


def test_a_two_letter_skill_passage_like_ai_ml_can_still_be_anchored() -> None:
    passages = (SourcePassage(field_name="skills", text="AI, ML"),)

    field = anchor_for("The candidate lists the following skills: AI, ML.", passages)

    assert field == "skills"


def test_a_tie_with_an_earlier_smaller_passage_anchors_to_the_richer_true_source() -> None:
    # Regression: build_source_passages() always orders passages skills/projects/experience/
    # education. An experience sentence naturally repeats the same skill names it mentions, so it
    # can cover 100% of the (smaller, earlier-checked) skills passage's tokens too -- a strict `>`
    # comparison let that earlier tie stand forever, mislabeling the experience sentence's source
    # as "skills". A human doing the monthly hallucination audit would check the wrong passage
    # (skills) and never verify the sentence's real claims (employer name, tenure) against the
    # actual experience passage they came from.
    passages = (
        SourcePassage(field_name="skills", text="Python, AWS, Docker"),
        SourcePassage(
            field_name="experience",
            text="Used Python, AWS and Docker daily while leading backend services at Acme Corp.",
        ),
    )
    sentence = (
        "Work experience: Used Python, AWS and Docker daily while leading backend "
        "services at Acme Corp.."
    )

    field = anchor_for(sentence, passages)

    assert field == "experience"


def test_short_token_passage_fallback_does_not_anchor_an_unrelated_sentence() -> None:
    # The relaxed fallback for short-token passages must still require real overlap -- it isn't a
    # blanket "anchor everything" escape hatch.
    passages = (SourcePassage(field_name="skills", text="Go, R, C"),)

    field = anchor_for("The candidate won a national chess championship in 2015.", passages)

    assert field is None
