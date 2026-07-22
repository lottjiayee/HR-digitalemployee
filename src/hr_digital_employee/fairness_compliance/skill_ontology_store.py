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


class SkillOntologyRepository:
    """Owns the skill-ontology/synonym mapping table. Every update is audit-logged (actor,
    timestamp, reason) -- Module 2 only ever reads the current state via `resolves_same_skill`.
    """

    def __init__(self, audit_log: AuditLog) -> None:
        self._audit_log = audit_log
        self._canonical: dict[str, str] = {}

    def add_synonym_group(self, group: tuple[str, ...], actor: str, reason: str) -> None:
        canonical = group[0].strip().lower()
        for term in group:
            self._canonical[term.strip().lower()] = canonical
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
        a_norm, b_norm = a.strip().lower(), b.strip().lower()
        return self._canonical.get(a_norm, a_norm) == self._canonical.get(b_norm, b_norm)
