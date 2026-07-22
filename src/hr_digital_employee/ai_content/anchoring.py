"""Sentence-to-source anchoring (FR-10): "every summary sentence carries a source-passage anchor;
unanchored sentences are dropped before output." This logic is provider-independent -- it applies
the same way regardless of which LLM eventually generates the sentences (design.md §10.2).

Checks how much of a *passage's* significant content shows up in a sentence, not the reverse --
lenient to a sentence's own framing/connector words (which a real LLM would add more of than this
codebase's template stub does), strict about whether the passage's real content actually appears.
"""

from __future__ import annotations

import re

from hr_digital_employee.ai_content.models import AnchoredSentence, SourcePassage

MIN_PASSAGE_COVERAGE = 0.5
"""Fraction of a passage's significant words that must appear in a sentence for it to count as
anchored to that passage. A judgement call, not a spec number -- see ASSUMPTIONS.md."""

_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "with",
        "is", "are", "was", "were", "be", "been", "this", "that", "these", "those",
    }
)

_WORD_PATTERN = re.compile(r"[a-z0-9]+")


def _significant_tokens(text: str) -> set[str]:
    return {
        token
        for token in _WORD_PATTERN.findall(text.lower())
        if len(token) >= 3 and token not in _STOPWORDS
    }


def anchor_for(sentence: str, passages: tuple[SourcePassage, ...]) -> str | None:
    """The field_name of the best-matching source passage, or None if no passage covers enough of
    `sentence` to count as anchored."""
    sentence_tokens = _significant_tokens(sentence)
    best_field: str | None = None
    best_coverage = 0.0
    for passage in passages:
        passage_tokens = _significant_tokens(passage.text)
        if not passage_tokens:
            continue
        coverage = len(passage_tokens & sentence_tokens) / len(passage_tokens)
        if coverage > best_coverage:
            best_coverage = coverage
            best_field = passage.field_name
    return best_field if best_coverage >= MIN_PASSAGE_COVERAGE else None


def anchor_sentences(
    sentences: tuple[str, ...], passages: tuple[SourcePassage, ...]
) -> tuple[AnchoredSentence, ...]:
    """Verify each candidate sentence against the source passages, dropping any that don't clear
    `MIN_PASSAGE_COVERAGE` against some passage (FR-10)."""
    anchored: list[AnchoredSentence] = []
    for sentence in sentences:
        field = anchor_for(sentence, passages)
        if field is not None:
            anchored.append(AnchoredSentence(text=sentence, source_field=field))
    return tuple(anchored)
