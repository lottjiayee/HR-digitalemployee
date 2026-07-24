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

_MIN_SIGNIFICANT_LENGTH = 3


def _tokens(text: str, *, min_length: int) -> set[str]:
    return {
        token
        for token in _WORD_PATTERN.findall(text.lower())
        if len(token) >= min_length and token not in _STOPWORDS
    }


def _significant_tokens(text: str) -> set[str]:
    return _tokens(text, min_length=_MIN_SIGNIFICANT_LENGTH)


def anchor_for(sentence: str, passages: tuple[SourcePassage, ...]) -> str | None:
    """The field_name of the best-matching source passage, or None if no passage covers enough of
    `sentence` to count as anchored."""
    best_field: str | None = None
    best_coverage = 0.0
    best_match_count = 0
    for passage in passages:
        passage_tokens = _significant_tokens(passage.text)
        min_length = _MIN_SIGNIFICANT_LENGTH
        if not passage_tokens:
            # A passage whose entire real content is short tokens (e.g. skills "Go", "R", "C",
            # "AI", "ML" -- all under the 3-character bar) has zero significant tokens and could
            # never be matched at all: confirmed this silently dropped a candidate's entire skills
            # sentence from the generated summary, even though it was verbatim, zero-hallucination-
            # risk real content. Falling back to every non-stopword token (any length) lets such a
            # passage still anchor -- only for passages this short, so ordinary passages keep the
            # stricter bar (avoiding stray 1-2 letter words inflating coverage elsewhere).
            passage_tokens = _tokens(passage.text, min_length=1)
            min_length = 1
        if not passage_tokens:
            continue
        # Tokenized at the same min_length as the passage: a short-token passage needs the
        # sentence's own short tokens (e.g. "Go") in play too, or the intersection is empty no
        # matter how verbatim the sentence actually is.
        sentence_tokens = _tokens(sentence, min_length=min_length)
        match_count = len(passage_tokens & sentence_tokens)
        coverage = match_count / len(passage_tokens)
        # A strict `>` here used to let the first-checked passage keep a tie forever -- and ties
        # are not rare: build_source_passages() always orders passages skills/projects/experience/
        # education, and a sentence generated from a *later* passage (e.g. experience) routinely
        # covers 100% of an *earlier*, smaller passage's tokens too (an experience narrative
        # naturally repeats the same skill names) -- confirmed a real experience sentence anchored
        # to "skills" instead of "experience" purely because skills happened to be checked first.
        # Breaking ties by the larger raw match count favors the richer, more specific passage --
        # the true source passage a sentence was generated from virtually always has at least as
        # much matching content as a smaller passage it happens to fully contain.
        if coverage > best_coverage or (
            coverage == best_coverage and match_count > best_match_count
        ):
            best_coverage = coverage
            best_match_count = match_count
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
