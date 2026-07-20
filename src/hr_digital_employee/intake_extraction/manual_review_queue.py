"""Manual-review queue for low-confidence/unparseable/ambiguous items (SOP 2.1.1, 2.1.3)."""

from __future__ import annotations

from hr_digital_employee.intake_extraction.models import ManualReviewItem


class ManualReviewQueue:
    """In-memory manual-review queue.

    A real deployment persists this and wires SLA monitoring (Module 7) -- this stub keeps
    Module 1 independently testable. See ASSUMPTIONS.md.
    """

    def __init__(self) -> None:
        self._items: list[ManualReviewItem] = []

    def enqueue(self, item: ManualReviewItem) -> None:
        self._items.append(item)

    def items(self) -> list[ManualReviewItem]:
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)
