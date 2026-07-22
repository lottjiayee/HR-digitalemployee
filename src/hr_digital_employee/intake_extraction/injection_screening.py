"""Untrusted-input screening before resume text reaches extraction or any LLM (SOP 2.1.2).

Strips hidden-text markup (white-on-white, near-zero font size) and flags instruction-like
patterns addressed to the system. This is a heuristic stub -- a production version would use a
more robust document-structure parser; see ASSUMPTIONS.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MAX_HIDDEN_SPAN = 300
"""Caps how far the paired-color pattern below can look between its opening and closing color
declaration. Without a bound, `.*?` with DOTALL matches between *any two* white-color CSS mentions
anywhere in the whole document -- two unrelated, ordinary style attributes (e.g. a decorative
header and a footer) would bridge everything in between and get stripped as "hidden text",
destroying real resume content that was never actually hidden (see ASSUMPTIONS.md). A genuine
hidden-instruction payload is realistically a sentence or two -- comfortably under this bound."""

_HIDDEN_TEXT_PATTERNS = [
    re.compile(
        rf"color:\s*#?(?:fff+|ffffff)\s*;.{{0,{_MAX_HIDDEN_SPAN}}}?color:\s*#?(?:fff+|ffffff)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(r"font-size:\s*0(?:\.\d+)?px[^\n]*", re.IGNORECASE),
]

_INSTRUCTION_LIKE_PATTERNS = [
    # Matches phrases like "ignore all previous instructions" -- qualifiers can stack, so the
    # group repeats rather than allowing exactly one of the alternatives.
    re.compile(r"ignore (?:all |any |previous |prior |the )*instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"you are now", re.IGNORECASE),
    re.compile(r"disregard (?:the|your) (?:scoring|rules|guidelines)", re.IGNORECASE),
]


@dataclass(frozen=True)
class ScreeningResult:
    cleaned_text: str
    suspected_injection: bool
    matched_patterns: list[str]


def screen(raw_text: str) -> ScreeningResult:
    """Strip hidden-text markup and flag instruction-like patterns (SOP 2.1.2)."""
    matched: list[str] = []
    cleaned = raw_text

    for pattern in _HIDDEN_TEXT_PATTERNS:
        if pattern.search(cleaned):
            matched.append(f"hidden_text:{pattern.pattern}")
        cleaned = pattern.sub(" ", cleaned)

    for pattern in _INSTRUCTION_LIKE_PATTERNS:
        if pattern.search(cleaned):
            matched.append(f"instruction_like:{pattern.pattern}")

    return ScreeningResult(
        cleaned_text=cleaned,
        suspected_injection=bool(matched),
        matched_patterns=matched,
    )
