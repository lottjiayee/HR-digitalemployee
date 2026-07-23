"""Pure data-layer for Module 5's comparison-table/drill-down dashboard (design.md §3.8, SOP
2.4.2-2.4.3). Wraps `pipeline.run_pipeline()` plus Module 3 content generation per candidate --
kept independent of Streamlit so it's testable without the `ui` extra installed, same spirit as
`jrp_editor/config_builder.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hr_digital_employee.ai_content.content_service import (
    ContentGenerationService,
    GeneratedContent,
)
from hr_digital_employee.governance_audit.interfaces import AuditLog
from hr_digital_employee.intake_extraction.interfaces import ExtractedResume
from hr_digital_employee.intake_extraction.manual_review_queue import ManualReviewQueue
from hr_digital_employee.intake_extraction.models import Candidate
from hr_digital_employee.pipeline import run_pipeline
from hr_digital_employee.scoring_engine.models import JRP, Score


@dataclass(frozen=True)
class DashboardRow:
    candidate: Candidate
    extracted: ExtractedResume
    score: Score
    content: GeneratedContent


def build_dashboard_rows(
    resumes_folder: Path, jrp: JRP, audit_log: AuditLog
) -> tuple[list[DashboardRow], ManualReviewQueue]:
    """Runs Modules 1+2 via the shared pipeline, then Module 3's content generation for every
    resulting candidate -- one row per candidate, sorted by score descending (inherited from
    `run_pipeline`)."""
    pipeline_results, manual_review_queue = run_pipeline(resumes_folder, jrp, audit_log)
    content_service = ContentGenerationService()
    rows = [
        DashboardRow(
            candidate=result.candidate,
            extracted=result.extracted,
            score=result.score,
            content=content_service.generate(
                result.candidate.candidate_id, result.extracted, result.score
            ),
        )
        for result in pipeline_results
    ]
    return rows, manual_review_queue


def summary_text(row: DashboardRow) -> str:
    return " ".join(sentence.text for sentence in row.content.summary.sentences)
