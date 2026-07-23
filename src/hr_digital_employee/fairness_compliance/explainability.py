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
    scoring or re-evaluation happens here.

    A failed must-have criterion is noted alongside the score, not in place of it (SOP 2.2.2/2.2.4,
    2026-07-22 revision) -- the candidate still sees the full basis for their result."""
    tier_label = score.tier.value.replace("_", " ")
    # Two decimals, not one: `engine.py` already rounds `total_score` to 2 places, and a value
    # like 79.95 displayed at 1 decimal ("80.0") sits right at the high_match boundary (80.0),
    # looking like a tier-classification bug even though "mid match" is correct -- the identical
    # regression already fixed in cli.py, just not ported here (round 6).
    summary = f"Overall score: {score.total_score:.2f}/100 ({tier_label}) for {jrp.role_name}."
    if not score.passed_must_have:
        reasons = "; ".join(score.failed_must_have_labels)
        summary += f" Must-have requirement(s) not met: {reasons}."
    dimension_explanations = tuple(
        f"{result.dimension.value.replace('_', ' ').title()}: {result.curve_score * 100:.0f}% "
        f"match, contributing {result.contribution:.1f} of {result.weight:.0f} possible points."
        for result in score.breakdown
    )
    return Explanation(summary=summary, dimension_explanations=dimension_explanations)
