"""Untrusted-input screening before resume text reaches extraction or any LLM (SOP 2.1.2).

Strips hidden-text markup (white-on-white, near-zero font size) and flags instruction-like
patterns addressed to the system. This is a heuristic stub -- a production version would use a
more robust document-structure parser; see ASSUMPTIONS.md.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_MAX_HIDDEN_SPAN = 300
"""Caps how far the paired-color pattern below can look between its opening and closing color
declaration. Without a bound, `.*?` with DOTALL matches between *any two* white-color CSS mentions
anywhere in the whole document -- two unrelated, ordinary style attributes (e.g. a decorative
header and a footer) would bridge everything in between and get stripped as "hidden text",
destroying real resume content that was never actually hidden (see ASSUMPTIONS.md). A genuine
hidden-instruction payload is realistically a sentence or two -- comfortably under this bound."""

_WHITE_COLOR = r"(?:#?(?:fff+|ffffff)|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\)|white)"
"""Recognizes the three ways a resume's HTML/CSS source realistically spells "white": hex
(`#fff`/`#ffffff`), `rgb(255,255,255)`, and the CSS named color `white` -- hex-only detection let a
real `rgb(255,255,255)` or `color:white` hidden-text payload through completely unflagged."""

_HIDDEN_TEXT_PATTERNS = [
    re.compile(
        rf"color:\s*{_WHITE_COLOR}\s*;?.{{0,{_MAX_HIDDEN_SPAN}}}?color:\s*{_WHITE_COLOR}",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(r"font-size:\s*0(?:\.\d+)?px[^\n]*", re.IGNORECASE),
]
# The opening color declaration's trailing `;` is optional (`;?`), not required: a white-color
# declaration that's the last (or only) rule before the closing quote (e.g. `style="color:#fff"`)
# has no trailing semicolon, and requiring one on the *opening* occurrence but not the closing one
# let that common, realistic form bypass detection entirely.

_ZERO_WIDTH_PATTERN = re.compile("[​‌‍⁠﻿]")
"""Zero-width space (U+200B), zero-width non-joiner (U+200C), zero-width joiner (U+200D), word
joiner (U+2060), and BOM/zero-width no-break space (U+FEFF) -- confirmed each one individually
defeats the instruction-like patterns below when inserted mid-keyword."""


def _normalize_for_instruction_matching(text: str) -> str:
    """Strips zero-width characters and combining diacritics before instruction-pattern matching
    only (never applied to `cleaned_text`, which must stay byte-for-byte the real resume content
    minus genuinely hidden text). A zero-width space/joiner inserted mid-keyword (e.g.
    "ign​ore") or a combining mark stacked onto a letter (e.g. "i̇gnore") renders
    identically to the plain word but was confirmed to silently defeat every instruction-like
    pattern below, since none of them tolerate an extra code point mid-match. This does not defend
    against homoglyph substitution (e.g. Cyrillic "о" for Latin "o") -- that would need a
    confusables table, out of scope for this heuristic stub; see ASSUMPTIONS.md."""
    without_zero_width = _ZERO_WIDTH_PATTERN.sub("", text)
    decomposed = unicodedata.normalize("NFD", without_zero_width)
    without_combining = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    return unicodedata.normalize("NFC", without_combining)


_INSTRUCTION_LIKE_PATTERNS = [
    # Matches phrases like "ignore all previous instructions" -- qualifiers can stack, so the
    # group repeats rather than allowing exactly one of the alternatives.
    re.compile(r"ignore (?:all |any |previous |prior |the )*instructions", re.IGNORECASE),
    # Anchored to the start of a line (ignoring leading whitespace): a chat-role-style injection
    # ("System: ignore your guidelines...") realistically opens its own line, whereas ordinary
    # resume content that just happens to contain the word "System" followed by a colon
    # ("Version Control System: Git, SVN", "Ticketing System: Jira") never has "system" as the
    # first word on the line -- confirmed the unanchored form flagged such ordinary skill lines as
    # suspected injection.
    re.compile(r"^\s*system\s*:\s*", re.IGNORECASE | re.MULTILINE),
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

    normalized_for_detection = _normalize_for_instruction_matching(cleaned)
    for pattern in _INSTRUCTION_LIKE_PATTERNS:
        if pattern.search(normalized_for_detection):
            matched.append(f"instruction_like:{pattern.pattern}")

    return ScreeningResult(
        cleaned_text=cleaned,
        suspected_injection=bool(matched),
        matched_patterns=matched,
    )
