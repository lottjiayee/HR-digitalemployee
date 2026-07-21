"""Skill-ontology-backed matching (FR-27, design.md §3.6): equivalent phrasings ("led a team" /
"team leadership") should resolve to the same skill so keyword matching isn't a language-bias
trap. design.md §3.6 says Module 4 owns and maintains the ontology table; the Scoring Engine only
reads it. Module 4 doesn't exist yet, so this module defines the read-only consumption point
(`SkillOntology`) plus two placeholder implementations. See ASSUMPTIONS.md.
"""

from __future__ import annotations

from typing import Protocol


class SkillOntology(Protocol):
    """Read-only lookup the Scoring Engine consumes; a real implementation is owned and
    maintained by Module 4 (design.md §3.6)."""

    def resolves_same_skill(self, a: str, b: str) -> bool: ...


class IdentitySkillOntology:
    """No synonym resolution -- exact, case/whitespace-insensitive match only. Default until
    Module 4 ships a real ontology; see ASSUMPTIONS.md."""

    def resolves_same_skill(self, a: str, b: str) -> bool:
        return a.strip().lower() == b.strip().lower()


class SynonymMapSkillOntology:
    """Minimal ontology backed by an explicit list of synonym groups, e.g.
    `[("led a team", "team leadership")]`. Placeholder for Module 4's real ontology/maintenance
    interface -- see ASSUMPTIONS.md."""

    def __init__(self, synonym_groups: list[tuple[str, ...]]) -> None:
        self._canonical: dict[str, str] = {}
        for group in synonym_groups:
            canonical = group[0].strip().lower()
            for term in group:
                self._canonical[term.strip().lower()] = canonical

    def resolves_same_skill(self, a: str, b: str) -> bool:
        a_norm, b_norm = a.strip().lower(), b.strip().lower()
        return self._canonical.get(a_norm, a_norm) == self._canonical.get(b_norm, b_norm)
