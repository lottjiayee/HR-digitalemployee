"""Tests for four-fifths adverse-impact testing (FR-20, test.md T4.1-T4.2)."""

from __future__ import annotations

import dataclasses

import pytest

from hr_digital_employee.fairness_compliance.adverse_impact import (
    AdverseImpactTestingService,
    four_fifths_test,
    standardized_difference_test,
)
from hr_digital_employee.fairness_compliance.models import GroupOutcome
from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog


def test_t4_1_a_70_percent_relative_rate_is_flagged() -> None:
    groups = (
        GroupOutcome(group_label="Group A", selected_count=70, total_count=100),  # 70% rate
        GroupOutcome(group_label="Group B", selected_count=100, total_count=100),  # 100% rate
    )

    result = four_fifths_test(groups)

    assert result.flagged is True
    assert result.impact_ratio == pytest.approx(0.7)
    assert result.lowest_rate_group == "Group A"
    assert result.highest_rate_group == "Group B"


def test_a_rate_at_exactly_80_percent_is_not_flagged() -> None:
    groups = (
        GroupOutcome(group_label="Group A", selected_count=80, total_count=100),
        GroupOutcome(group_label="Group B", selected_count=100, total_count=100),
    )

    assert four_fifths_test(groups).flagged is False


def test_four_fifths_test_requires_at_least_two_groups() -> None:
    with pytest.raises(ValueError, match="at least two groups"):
        four_fifths_test((GroupOutcome(group_label="Solo", selected_count=1, total_count=1),))


def test_t4_2_a_flag_from_a_small_sample_is_not_corroborated_by_significance() -> None:
    # Same 70%-vs-100% relative gap as T4.1, but tiny sample -- shouldn't be statistically
    # significant, so the four-fifths flag should not yet be treated as conclusive.
    small_a = GroupOutcome(group_label="Group A", selected_count=7, total_count=10)
    small_b = GroupOutcome(group_label="Group B", selected_count=10, total_count=10)

    result = standardized_difference_test(small_a, small_b)

    assert result.significant is False


def test_a_flag_from_a_large_sample_is_corroborated_by_significance() -> None:
    large_a = GroupOutcome(group_label="Group A", selected_count=700, total_count=1000)
    large_b = GroupOutcome(group_label="Group B", selected_count=1000, total_count=1000)

    result = standardized_difference_test(large_a, large_b)

    assert result.significant is True


def test_identical_rates_are_never_significant() -> None:
    a = GroupOutcome(group_label="A", selected_count=50, total_count=100)
    b = GroupOutcome(group_label="B", selected_count=50, total_count=100)

    result = standardized_difference_test(a, b)

    assert result.z_score == 0.0
    assert result.significant is False


def test_group_outcome_rejects_zero_total() -> None:
    with pytest.raises(ValueError, match="total_count"):
        GroupOutcome(group_label="Empty", selected_count=0, total_count=0)


def test_group_outcome_rejects_selected_greater_than_total() -> None:
    with pytest.raises(ValueError, match="selected_count"):
        GroupOutcome(group_label="Bad", selected_count=5, total_count=3)


def test_all_groups_at_zero_selection_rate_is_not_flagged() -> None:
    # Regression test: nobody has been selected in any group yet (e.g. a brand-new JRP with zero
    # hires so far) -- every group is equally at 0%, so there's no disparity to flag, even though
    # naively dividing by a zero highest-rate would otherwise force impact_ratio to 0.0.
    groups = (
        GroupOutcome(group_label="Group A", selected_count=0, total_count=50),
        GroupOutcome(group_label="Group B", selected_count=0, total_count=50),
    )

    result = four_fifths_test(groups)

    assert result.flagged is False
    assert result.impact_ratio == 1.0


def test_an_intermediate_group_violation_is_not_masked_by_only_reporting_the_extreme_pair() -> (
    None
):
    # Regression (round 6): with more than two groups, only the single lowest-rate group was
    # named -- a middle group that itself violates the four-fifths threshold relative to the
    # highest (but isn't the extreme lowest) went unreported. Group C here independently has an
    # impact ratio of 0.79 (fails), distinct from Group B (the extreme lowest, ratio 0.4).
    groups = (
        GroupOutcome(group_label="White", selected_count=50, total_count=100),  # 50% (highest)
        GroupOutcome(group_label="Black", selected_count=20, total_count=100),  # 20%, ratio 0.4
        GroupOutcome(group_label="Hispanic", selected_count=39, total_count=100),  # 39%, ratio .78
    )

    result = four_fifths_test(groups)

    assert result.lowest_rate_group == "Black"
    assert "Black" in result.violating_groups
    assert "Hispanic" in result.violating_groups
    assert "White" not in result.violating_groups


def test_no_violating_groups_when_every_group_clears_the_threshold() -> None:
    groups = (
        GroupOutcome(group_label="A", selected_count=90, total_count=100),
        GroupOutcome(group_label="B", selected_count=100, total_count=100),
    )

    result = four_fifths_test(groups)

    assert result.violating_groups == ()


def test_adverse_impact_testing_service_audit_logs_a_flagged_result() -> None:
    audit_log = InMemoryAuditLog()
    service = AdverseImpactTestingService(audit_log)
    groups = (
        GroupOutcome(group_label="Group A", selected_count=70, total_count=100),
        GroupOutcome(group_label="Group B", selected_count=100, total_count=100),
    )

    result = service.run_four_fifths_test(
        "jrp-1", groups, actor="fairness_job", reason="quarterly re-test"
    )

    assert result.flagged is True
    events = audit_log.events_for("jrp-1")
    assert len(events) == 1
    assert events[0].action == "fairness_flag_raised"
    assert "quarterly re-test" in events[0].reason


def test_zero_selection_rate_in_both_groups_is_not_significant() -> None:
    # Regression: pooled_rate == 0 makes standard_error's variance term (pooled_rate * (1 -
    # pooled_rate)) zero, the same division-by-zero shape four_fifths_test's own zero-rate guard
    # protects against -- this exercises standardized_difference_test's separate guard for it.
    a = GroupOutcome(group_label="A", selected_count=0, total_count=50)
    b = GroupOutcome(group_label="B", selected_count=0, total_count=50)

    result = standardized_difference_test(a, b)

    assert result.z_score == 0.0
    assert result.significant is False


def test_full_selection_rate_in_both_groups_is_not_significant() -> None:
    # Same guard, opposite edge: pooled_rate == 1 also zeroes the variance term.
    a = GroupOutcome(group_label="A", selected_count=50, total_count=50)
    b = GroupOutcome(group_label="B", selected_count=50, total_count=50)

    result = standardized_difference_test(a, b)

    assert result.z_score == 0.0
    assert result.significant is False


def test_t4_4_fourfifths_result_carries_no_individual_level_data() -> None:
    # FR-21/T4.4: fairness output must be aggregate-only -- never reconstructing an individual's
    # protected attributes. Asserted structurally: the result type has no candidate identifier or
    # per-individual field, only group labels and an aggregate ratio.
    groups = (
        GroupOutcome(group_label="Group A", selected_count=70, total_count=100),
        GroupOutcome(group_label="Group B", selected_count=100, total_count=100),
    )

    result = four_fifths_test(groups)

    result_fields = {f.name for f in dataclasses.fields(result)}
    assert result_fields == {
        "flagged",
        "lowest_rate_group",
        "highest_rate_group",
        "impact_ratio",
        "violating_groups",
    }
    assert "candidate_id" not in result_fields


def test_adverse_impact_testing_service_audit_logs_a_passing_result_too() -> None:
    # md/prompt.md invariant 5 requires every decision-relevant output logged, not just the
    # flagged ones -- a "no impact detected" result is still decision-relevant.
    audit_log = InMemoryAuditLog()
    service = AdverseImpactTestingService(audit_log)
    groups = (
        GroupOutcome(group_label="Group A", selected_count=95, total_count=100),
        GroupOutcome(group_label="Group B", selected_count=100, total_count=100),
    )

    result = service.run_four_fifths_test("jrp-1", groups, actor="fairness_job", reason="test")

    assert result.flagged is False
    assert audit_log.events_for("jrp-1")[0].action == "fairness_test_passed"
