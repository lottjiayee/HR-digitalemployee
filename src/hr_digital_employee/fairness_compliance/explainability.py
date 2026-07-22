"""Explainability-on-request (FR-25): a human-readable explanation derived from an existing
`Score` (the Matching Analysis) only -- this must never re-score or re-derive a result, only
explain the one Module 2 already produced (module-4 doc §4).
"""

from __future__ import annotations

from dataclasses import dataclass

from hr_digital_employee.scoring_engine.interfaces import JRP, Score


@dataclass(frozen=True)
class Explanation:
    summary: str
    dimension_explanations: tuple[str, ...]


def explain_score(score: Score, jrp: JRP) -> Explanation:
    """Read-only: consumes `score.breakdown` exactly as Module 2 produced it (FR-25). No new
    scoring or re-evaluation happens here."""
    if not score.passed_must_have:
        return Explanation(
            summary=(
                f"This application did not proceed to full scoring because a must-have "
                f"requirement was not met: {score.failed_must_have_label}."
            ),
            dimension_explanations=(),
        )

    tier_label = score.tier.value.replace("_", " ")
    summary = f"Overall score: {score.total_score:.1f}/100 ({tier_label}) for {jrp.role_name}."
    dimension_explanations = tuple(
        f"{result.dimension.value.replace('_', ' ').title()}: {result.curve_score * 100:.0f}% "
        f"match, contributing {result.contribution:.1f} of {result.weight:.0f} possible points."
        for result in score.breakdown
    )
    return Explanation(summary=summary, dimension_explanations=dimension_explanations)
