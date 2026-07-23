"""Tests for Module 5's dashboard data layer (design.md §3.8, SOP 2.4.2-2.4.3)."""

from __future__ import annotations

from pathlib import Path

from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog
from hr_digital_employee.presentation.dashboard_data import (
    build_dashboard_rows,
    build_dashboard_rows_from_uploads,
    summary_text,
)
from hr_digital_employee.scoring_engine.jrp_config import load_jrp_from_yaml

JRP_CONFIG = """
jrp_id: backend-engineer
role_name: Backend Engineer
version: 1
weight_template: general

weighted_criteria:
  - dimension: mandatory_skills
    curve: linear
    required_skills: [Python, SQL]
  - dimension: experience_tenure
    curve: linear
    required_years: 5
  - dimension: educational_level
    curve: linear
    required_education_level: bachelor
  - dimension: project_relevance
    curve: linear
    required_project_count: 2
"""

STRONG_RESUME = (
    b"Skills:\nPython\nSQL\n\n"
    b"Projects:\nBuilt a data pipeline\nLed a small team\n\n"
    b"Working Experience:\n5 years at TechCorp as a backend engineer\n\n"
    b"Education:\nBachelor of Computer Science\n"
)


def test_build_dashboard_rows_includes_score_and_generated_content(tmp_path: Path) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "candidate.pdf").write_bytes(STRONG_RESUME)
    jrp_path = tmp_path / "backend-engineer.yaml"
    jrp_path.write_text(JRP_CONFIG, encoding="utf-8")
    jrp = load_jrp_from_yaml(jrp_path)

    rows, manual_review_queue = build_dashboard_rows(resumes_dir, jrp, InMemoryAuditLog())

    assert len(rows) == 1
    assert len(manual_review_queue) == 0
    row = rows[0]
    assert row.score.total_score == 100.0
    assert row.content.summary.sentences
    assert summary_text(row) != ""


def test_build_dashboard_rows_is_empty_for_a_folder_with_no_resumes(tmp_path: Path) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    jrp_path = tmp_path / "backend-engineer.yaml"
    jrp_path.write_text(JRP_CONFIG, encoding="utf-8")
    jrp = load_jrp_from_yaml(jrp_path)

    rows, manual_review_queue = build_dashboard_rows(resumes_dir, jrp, InMemoryAuditLog())

    assert rows == []
    assert len(manual_review_queue) == 0


def test_build_dashboard_rows_from_uploads_includes_score_and_generated_content(
    tmp_path: Path,
) -> None:
    jrp_path = tmp_path / "backend-engineer.yaml"
    jrp_path.write_text(JRP_CONFIG, encoding="utf-8")
    jrp = load_jrp_from_yaml(jrp_path)

    rows, manual_review_queue = build_dashboard_rows_from_uploads(
        [("candidate.pdf", STRONG_RESUME)], jrp, InMemoryAuditLog()
    )

    assert len(rows) == 1
    assert len(manual_review_queue) == 0
    row = rows[0]
    assert row.score.total_score == 100.0
    assert row.content.summary.sentences
    assert summary_text(row) != ""


def test_build_dashboard_rows_from_uploads_is_empty_for_an_empty_upload_list(
    tmp_path: Path,
) -> None:
    jrp_path = tmp_path / "backend-engineer.yaml"
    jrp_path.write_text(JRP_CONFIG, encoding="utf-8")
    jrp = load_jrp_from_yaml(jrp_path)

    rows, manual_review_queue = build_dashboard_rows_from_uploads([], jrp, InMemoryAuditLog())

    assert rows == []
    assert len(manual_review_queue) == 0


def test_build_dashboard_rows_from_uploads_matches_the_folder_based_result_for_the_same_resume(
    tmp_path: Path,
) -> None:
    # Consistency guarantee (SOP 2.1.1): the same resume bytes must score identically whether they
    # arrive via the folder-path adapter or the in-memory upload adapter -- these are two channel
    # adapters feeding the same extraction/scoring pipeline, not two different pipelines.
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "candidate.pdf").write_bytes(STRONG_RESUME)
    jrp_path = tmp_path / "backend-engineer.yaml"
    jrp_path.write_text(JRP_CONFIG, encoding="utf-8")
    jrp = load_jrp_from_yaml(jrp_path)

    folder_rows, _ = build_dashboard_rows(resumes_dir, jrp, InMemoryAuditLog())
    upload_rows, _ = build_dashboard_rows_from_uploads(
        [("candidate.pdf", STRONG_RESUME)], jrp, InMemoryAuditLog()
    )

    assert folder_rows[0].score.total_score == upload_rows[0].score.total_score == 100.0
    assert folder_rows[0].extracted.skills.value == upload_rows[0].extracted.skills.value
