"""Skill-ontology maintenance (FR-27; module-4 doc §4): "this module owns updates to the
ontology; Module 2 never writes to it."

`SkillOntologyRepository.resolves_same_skill()` structurally satisfies
`scoring_engine.skill_ontology.SkillOntology` (a `Protocol`) without this module importing
anything from `scoring_engine` -- whatever wires up a real `ScoringEngine` instance passes a
repository instance as its `skill_ontology` argument. This keeps the dependency direction matching
module-4 doc §5 ("Downstream: Module 7... "; Module 2 is a *consumer*, not a dependency of this
module) -- see ASSUMPTIONS.md.
"""

from __future__ import annotations

from datetime import UTC, datetime

from hr_digital_employee.governance_audit.interfaces import AuditEvent, AuditLog


def _normalize(skill: str) -> str:
    """Case-insensitive *and* whitespace-insensitive: collapses any run of internal whitespace to
    a single space, not just leading/trailing (`.strip()` alone would miss e.g. a doubled internal
    space)."""
    return " ".join(skill.split()).lower()


class SkillOntologyRepository:
    """Owns the skill-ontology/synonym mapping table. Every update is audit-logged (actor,
    timestamp, reason) -- Module 2 only ever reads the current state via `resolves_same_skill`.
    """

    def __init__(self, audit_log: AuditLog) -> None:
        self._audit_log = audit_log
        self._canonical: dict[str, str] = {}

    def add_synonym_group(self, group: tuple[str, ...], actor: str, reason: str) -> None:
        canonical = _normalize(group[0])
        for term in group:
            normalized_term = _normalize(term)
            existing_canonical = self._canonical.get(normalized_term)
            if existing_canonical is not None and existing_canonical != canonical:
                # Without this check, a later group sharing a term with an earlier one would
                # silently overwrite that term's mapping -- breaking the earlier group's
                # synonymy with no error and no audit trace of the corruption at all.
                raise ValueError(
                    f"{term!r} is already mapped to synonym group {existing_canonical!r}; cannot "
                    f"also add it to group {canonical!r} -- synonym groups must not overlap"
                )
        for term in group:
            self._canonical[_normalize(term)] = canonical
        self._audit_log.record(
            AuditEvent(
                actor=actor,
                entity_ref="skill-ontology",
                action="synonym_group_added",
                reason=reason,
                timestamp=datetime.now(UTC),
                version=str(len(self._canonical)),
            )
        )

    def resolves_same_skill(self, a: str, b: str) -> bool:
        """Read-only lookup Module 2's `ScoringEngine` consumes (T4.13)."""
        a_norm, b_norm = _normalize(a), _normalize(b)
        return self._canonical.get(a_norm, a_norm) == self._canonical.get(b_norm, b_norm)
