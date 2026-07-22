"""Jurisdiction layering (module-4 doc §4): PDPO baseline, GDPR for EU candidates, PIPL for
Mainland China candidates, default to the strictest framework when jurisdiction can't be
determined. Actual jurisdiction *detection* (geo/IP, declared address, etc.) needs real
integration data this codebase doesn't have yet -- flagged, not stubbed, same as Module 1's
malware scanning; see ASSUMPTIONS.md. The *default-when-undetermined* decision is pure logic and
is built for real.
"""

from __future__ import annotations

from hr_digital_employee.fairness_compliance.models import Jurisdiction

STRICTEST_DEFAULT = Jurisdiction.EU_GDPR
"""GDPR (with its Article 22 automated-decision rights) is treated as the strictest baseline when
a candidate's jurisdiction can't be determined. A judgement call, not a spec-given ranking between
PDPO/GDPR/PIPL -- see ASSUMPTIONS.md."""


def resolve_jurisdiction(declared: Jurisdiction) -> Jurisdiction:
    """The jurisdiction whose rules should actually govern this candidate's data -- defaults to
    `STRICTEST_DEFAULT` when `declared` is `UNDETERMINED`, otherwise returns it unchanged."""
    if declared is Jurisdiction.UNDETERMINED:
        return STRICTEST_DEFAULT
    return declared
