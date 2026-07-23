"""Four-fifths rule adverse-impact testing (FR-20; module-4 doc §4).

Four-fifths is a trigger, not a verdict -- `standardized_difference_test` corroborates a flag with
a two-proportion z-test before it's treated as conclusive, per module-4 doc §4's explicit guidance.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from hr_digital_employee.fairness_compliance.models import (
    FourFifthsResult,
    GroupOutcome,
    SignificanceResult,
)
from hr_digital_employee.governance_audit.interfaces import AuditEvent, AuditLog

FOUR_FIFTHS_THRESHOLD = 0.8
"""FR-20: a group's selection rate below this fraction of the highest group's rate is flagged."""

SIGNIFICANCE_Z_CRITICAL = 1.96
"""Two-tailed critical value for p < 0.05 -- a standard, well-known threshold, chosen so this
doesn't need a scipy dependency just to corroborate a four-fifths flag."""


def four_fifths_test(groups: tuple[GroupOutcome, ...]) -> FourFifthsResult:
    if len(groups) < 2:
        raise ValueError("four-fifths test needs at least two groups to compare")

    highest = max(groups, key=lambda g: g.selection_rate)
    lowest = min(groups, key=lambda g: g.selection_rate)

    if highest.selection_rate == 0:
        # Nobody was selected in any group -- every group is equally at 0%, so there is no
        # disparity to measure, not a maximal one. Forcing impact_ratio to 0.0 here would flag a
        # JRP with zero hires so far as if it had the worst possible adverse impact.
        impact_ratio = 1.0
        violating_groups: tuple[str, ...] = ()
    else:
        impact_ratio = lowest.selection_rate / highest.selection_rate
        # Every group below the threshold relative to the highest, not just the single lowest --
        # with more than two groups, a middle group can independently violate four-fifths without
        # being the extreme lowest one, and reporting only the lowest/highest pair let that
        # violation go unreported to anyone who didn't separately re-derive it themselves.
        violating_groups = tuple(
            group.group_label
            for group in groups
            if group is not highest
            and group.selection_rate / highest.selection_rate < FOUR_FIFTHS_THRESHOLD
        )

    return FourFifthsResult(
        flagged=impact_ratio < FOUR_FIFTHS_THRESHOLD,
        lowest_rate_group=lowest.group_label,
        highest_rate_group=highest.group_label,
        impact_ratio=impact_ratio,
        violating_groups=violating_groups,
    )


def standardized_difference_test(
    group_a: GroupOutcome, group_b: GroupOutcome
) -> SignificanceResult:
    """Two-proportion z-test between the two groups' selection rates."""
    n1, n2 = group_a.total_count, group_b.total_count
    pooled_rate = (group_a.selected_count + group_b.selected_count) / (n1 + n2)
    standard_error = math.sqrt(pooled_rate * (1 - pooled_rate) * (1 / n1 + 1 / n2))

    if standard_error == 0:
        return SignificanceResult(z_score=0.0, significant=False)

    z_score = (group_a.selection_rate - group_b.selection_rate) / standard_error
    return SignificanceResult(z_score=z_score, significant=abs(z_score) >= SIGNIFICANCE_Z_CRITICAL)


class AdverseImpactTestingService:
    """Runs four-fifths testing and audit-logs the outcome. md/prompt.md §2 invariant 5: every
    decision-relevant output -- including a fairness flag -- must emit an audit event through
    `governance_audit`, never an ad hoc log. `four_fifths_test`/`standardized_difference_test`
    stay pure functions (easy to unit-test without an audit log); this service is the thin
    audit-logging wrapper around them, the same shape as `scoring_engine.JRPRepository`."""

    def __init__(self, audit_log: AuditLog) -> None:
        self._audit_log = audit_log

    def run_four_fifths_test(
        self, jrp_id: str, groups: tuple[GroupOutcome, ...], actor: str, reason: str
    ) -> FourFifthsResult:
        result = four_fifths_test(groups)
        self._audit_log.record(
            AuditEvent(
                actor=actor,
                entity_ref=jrp_id,
                action="fairness_flag_raised" if result.flagged else "fairness_test_passed",
                reason=(
                    f"{reason}; impact ratio {result.impact_ratio:.2f} between "
                    f"{result.lowest_rate_group!r} and {result.highest_rate_group!r}"
                ),
                timestamp=datetime.now(UTC),
                version="1",
            )
        )
        return result
