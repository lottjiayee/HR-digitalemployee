"""Monthly hallucination-audit support (module-3 doc §4/§6, FR-10): a query/export hook this
module must support, not perform itself -- the actual comparison of summaries vs. source resumes
is a human/operational process (design.md §3.5).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from hr_digital_employee.ai_content.models import CandidateSummary, SourcePassage


@dataclass(frozen=True)
class AuditableSummary:
    candidate_id: str
    summary: CandidateSummary
    source_passages: tuple[SourcePassage, ...]


class HallucinationAuditLog:
    """Records every generated summary alongside its source passages so a human reviewer can
    later sample and compare them against the original resumes."""

    def __init__(self) -> None:
        self._entries: list[AuditableSummary] = []

    def record(
        self,
        candidate_id: str,
        summary: CandidateSummary,
        source_passages: tuple[SourcePassage, ...],
    ) -> None:
        self._entries.append(
            AuditableSummary(
                candidate_id=candidate_id, summary=summary, source_passages=source_passages
            )
        )

    def sample(self, size: int) -> list[AuditableSummary]:
        """A random sample of at most `size` recorded summaries, alongside their source passages,
        for manual comparison against the original resumes."""
        return random.sample(self._entries, k=min(size, len(self._entries)))

    def __len__(self) -> int:
        return len(self._entries)


def is_suspension_triggered(hallucination_rate: float, threshold: float) -> bool:
    """True if a measured hallucination rate breaches `threshold` and the service should suspend.

    module-3 doc §6: the actual threshold number is an unresolved, real-world decision (SOP 2.3.1
    references "the agreed threshold" without a figure) -- this function does not default to a
    number nobody has agreed on; callers must supply one explicitly.
    """
    return hallucination_rate > threshold
