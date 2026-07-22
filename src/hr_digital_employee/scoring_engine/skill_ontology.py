"""Skill-ontology-backed matching (FR-27, design.md §3.6): equivalent phrasings ("led a team" /
"team leadership") should resolve to the same skill so keyword matching isn't a language-bias
trap. design.md §3.6 says Module 4 owns and maintains the ontology table; the Scoring Engine only
reads it. Module 4 doesn't exist yet, so this module defines the read-only consumption point
(`SkillOntology`) plus two placeholder implementations. See ASSUMPTIONS.md.
"""

from __future__ import annotations

from typing import Protocol


def _normalize(skill: str) -> str:
    """Case-insensitive *and* whitespace-insensitive: `.split()`/`" ".join(...)` collapses any
    run of internal whitespace to a single space (not just leading/trailing), so e.g. "Team
    Leadership" with a doubled internal space still matches "Team Leadership" -- `.strip()` alone
    only trims the ends and would otherwise leave the two looking like different skills."""
    return " ".join(skill.split()).lower()


class SkillOntology(Protocol):
    """Read-only lookup the Scoring Engine consumes; a real implementation is owned and
    maintained by Module 4 (design.md §3.6)."""

    def resolves_same_skill(self, a: str, b: str) -> bool: ...


class IdentitySkillOntology:
    """No synonym resolution -- exact, case/whitespace-insensitive match only. Default until
    Module 4 ships a real ontology; see ASSUMPTIONS.md."""

    def resolves_same_skill(self, a: str, b: str) -> bool:
        return _normalize(a) == _normalize(b)


class SynonymMapSkillOntology:
    """Minimal ontology backed by an explicit list of synonym groups, e.g.
    `[("led a team", "team leadership")]`. Placeholder for Module 4's real ontology/maintenance
    interface -- see ASSUMPTIONS.md."""

    def __init__(self, synonym_groups: list[tuple[str, ...]]) -> None:
        self._canonical: dict[str, str] = {}
        for group in synonym_groups:
            canonical = _normalize(group[0])
            for term in group:
                normalized_term = _normalize(term)
                existing_canonical = self._canonical.get(normalized_term)
                if existing_canonical is not None and existing_canonical != canonical:
                    # Without this check, a later group sharing a term with an earlier one would
                    # silently overwrite that term's mapping -- breaking the earlier group's
                    # synonymy with no error and no trace of what changed (see ASSUMPTIONS.md).
                    raise ValueError(
                        f"{term!r} is already mapped to synonym group {existing_canonical!r}; "
                        f"cannot also add it to group {canonical!r} -- synonym groups must not "
                        "overlap"
                    )
                self._canonical[normalized_term] = canonical

    def resolves_same_skill(self, a: str, b: str) -> bool:
        a_norm, b_norm = _normalize(a), _normalize(b)
        return self._canonical.get(a_norm, a_norm) == self._canonical.get(b_norm, b_norm)
