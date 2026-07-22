"""Tests for JRP storage and change auditing (module-2-scoring-engine.md §4)."""

from __future__ import annotations

import pytest

from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog
from hr_digital_employee.scoring_engine.jrp_repository import JRPRepository
from hr_digital_employee.scoring_engine.models import (
    JRP,
    Dimension,
    EducationLevel,
    MatchingCurve,
    WeightedCriterion,
    WeightTemplate,
)


def _jrp(version: int = 1) -> JRP:
    return JRP(
        jrp_id="role-1",
        role_name="Senior Engineer",
        version=version,
        weight_template=WeightTemplate.GENERAL,
        weighted_criteria=(
            WeightedCriterion(
                dimension=Dimension.MANDATORY_SKILLS,
                weight=100.0,
                curve=MatchingCurve.LINEAR,
                required_skills=("Python",),
            ),
        ),
    )


def test_save_records_a_jrp_saved_audit_event() -> None:
    audit_log = InMemoryAuditLog()
    repo = JRPRepository(audit_log)

    repo.save(_jrp(), actor="hr_alice", reason="initial JRP for Senior Engineer role")

    events = audit_log.events_for("role-1")
    assert len(events) == 1
    assert events[0].action == "jrp_saved"
    assert events[0].actor == "hr_alice"
    assert events[0].version == "1"


def test_get_returns_the_most_recently_saved_version() -> None:
    audit_log = InMemoryAuditLog()
    repo = JRPRepository(audit_log)

    repo.save(_jrp(version=1), actor="hr_alice", reason="initial")
    repo.save(_jrp(version=2), actor="hr_alice", reason="widened weights")

    jrp = repo.get("role-1")
    assert jrp is not None
    assert jrp.version == 2
    assert len(audit_log.events_for("role-1")) == 2


def test_get_returns_none_for_an_unknown_jrp() -> None:
    repo = JRPRepository(InMemoryAuditLog())

    assert repo.get("does-not-exist") is None


def test_save_audit_logs_a_guideline_warning_when_educational_level_weight_is_high() -> None:
    audit_log = InMemoryAuditLog()
    repo = JRPRepository(audit_log)
    jrp = JRP(
        jrp_id="role-2",
        role_name="Graduate Analyst",
        version=1,
        weight_template=WeightTemplate.JUNIOR_GRADUATE,
        weighted_criteria=(
            WeightedCriterion(
                dimension=Dimension.EDUCATIONAL_LEVEL,
                weight=100.0,  # well above the 15% guideline default
                curve=MatchingCurve.LINEAR,
                required_education_level=EducationLevel.BACHELOR,
            ),
        ),
    )

    repo.save(jrp, actor="hr_alice", reason="graduate role JRP")

    warning_events = [
        e for e in audit_log.events_for("role-2") if e.action == "jrp_weight_guideline_warning"
    ]
    assert len(warning_events) == 1
    assert "Educational Level" in warning_events[0].reason


def test_save_does_not_audit_log_a_warning_when_weights_are_within_guideline() -> None:
    audit_log = InMemoryAuditLog()
    repo = JRPRepository(audit_log)

    repo.save(_jrp(), actor="hr_alice", reason="initial")

    warning_events = [
        e for e in audit_log.events_for("role-1") if e.action == "jrp_weight_guideline_warning"
    ]
    assert warning_events == []


def test_saving_a_lower_version_over_a_higher_one_is_rejected() -> None:
    # Regression: save() had no version-monotonicity check at all -- an accidental save of an
    # older/duplicate version silently overwrote a newer one, with only a forensic (not
    # preventive) audit trail; any candidate scored via get() afterward was silently scored
    # against stale criteria.
    audit_log = InMemoryAuditLog()
    repo = JRPRepository(audit_log)
    repo.save(_jrp(version=3), actor="hr_alice", reason="v3")

    with pytest.raises(ValueError, match="must strictly increase"):
        repo.save(_jrp(version=1), actor="hr_alice", reason="oops, v1 again")

    assert repo.get("role-1").version == 3  # type: ignore[union-attr]


def test_saving_the_same_version_again_is_rejected() -> None:
    audit_log = InMemoryAuditLog()
    repo = JRPRepository(audit_log)
    repo.save(_jrp(version=1), actor="hr_alice", reason="initial")

    with pytest.raises(ValueError, match="must strictly increase"):
        repo.save(_jrp(version=1), actor="hr_alice", reason="duplicate save")


def test_save_does_not_store_the_jrp_if_audit_logging_fails() -> None:
    # Regression: the store write happened *before* the audit-log call, so a failure recording
    # the audit event still left the new JRP live with no corresponding audit trail entry at all
    # -- directly undermining "every JRP change is audit-logged."
    class _RaisingAuditLog:
        def record(self, event: object) -> None:
            raise RuntimeError("simulated audit log failure")

        def events_for(self, entity_ref: str) -> list[object]:
            return []

        def all_events(self) -> list[object]:
            return []

    repo = JRPRepository(_RaisingAuditLog())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError):
        repo.save(_jrp(version=1), actor="hr_alice", reason="initial")

    assert repo.get("role-1") is None
