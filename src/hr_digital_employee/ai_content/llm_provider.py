"""The second LLM provider (design.md §10.2, §1.1) -- a single-shot, tightly-scoped API call, not
an autonomous agent (Manus, Module 6's concern, is out of scope here). Which vendor (Claude,
OpenAI, Azure OpenAI, other) is still an open decision; see ASSUMPTIONS.md.

This module defines the interface every provider must satisfy and ships a local, deterministic
stub so the rest of the pipeline (anchoring, question generation, red-flag detection, version
stamping) is fully testable without an API key or network call.
"""

from __future__ import annotations

from typing import Protocol

from hr_digital_employee.ai_content.models import SourcePassage


class LLMProvider(Protocol):
    """Generates candidate-summary sentences from structured source passages only -- never given
    raw resume text or LLM-Assisted output any downstream consumer could mistake for scoring
    input."""

    def generate_summary_sentences(
        self, passages: tuple[SourcePassage, ...]
    ) -> tuple[str, ...]: ...


class TemplateLLMProvider:
    """Deterministic, offline stand-in for a real LLM call: turns each non-empty source passage
    into one factual sentence built directly from its own text, so every sentence is anchorable
    by construction. Not a real generation model -- see ASSUMPTIONS.md.
    """

    def generate_summary_sentences(self, passages: tuple[SourcePassage, ...]) -> tuple[str, ...]:
        sentences = []
        for passage in passages:
            if not passage.text.strip():
                continue
            sentences.append(_sentence_for(passage))
        return tuple(sentences)


def _sentence_for(passage: SourcePassage) -> str:
    text = passage.text.strip().replace("\n", "; ")
    if passage.field_name == "skills":
        return f"The candidate lists the following skills: {text}."
    if passage.field_name == "projects":
        return f"Notable projects include: {text}."
    if passage.field_name == "experience":
        return f"Work experience: {text}."
    if passage.field_name == "education":
        return f"Education: {text}."
    return f"{passage.field_name.replace('_', ' ').capitalize()}: {text}."
