"""Tests for the shared Module 1 -> Module 2 pipeline runner (src/hr_digital_employee/pipeline.py)
used by both cli.py and Module 5's dashboard.
"""

from __future__ import annotations

from pathlib import Path

from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog
from hr_digital_employee.intake_extraction.models import Candidate
from hr_digital_employee.pipeline import candidate_label, run_pipeline
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

WEAKER_RESUME = (
    b"Skills:\nPython\nSQL\n\nProjects:\nOne project\n\n"
    b"Working Experience:\n2 years at StartCo\n\nEducation:\nBachelor of Arts\n"
)


def test_run_pipeline_returns_results_sorted_by_score_descending(tmp_path: Path) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "strong.pdf").write_bytes(STRONG_RESUME)
    (resumes_dir / "weaker.pdf").write_bytes(WEAKER_RESUME)
    jrp_path = tmp_path / "backend-engineer.yaml"
    jrp_path.write_text(JRP_CONFIG, encoding="utf-8")
    jrp = load_jrp_from_yaml(jrp_path)

    results, manual_review_queue = run_pipeline(resumes_dir, jrp, InMemoryAuditLog())

    assert len(results) == 2
    assert len(manual_review_queue) == 0
    assert results[0].score.total_score >= results[1].score.total_score
    assert results[0].extracted.skills.value is not None


def test_candidate_label_falls_back_through_name_email_phone_id() -> None:
    named = Candidate(candidate_id="id-1", email="a@example.com", phone="555", name="Jane Doe")
    assert candidate_label(named) == "Jane Doe"

    unnamed = Candidate(candidate_id="id-2", email="a@example.com", phone="555", name=None)
    assert candidate_label(unnamed) == "a@example.com"

    only_id = Candidate(candidate_id="id-3", email=None, phone=None, name=None)
    assert candidate_label(only_id) == "id-3"


def test_candidate_label_strips_embedded_newlines() -> None:
    # A label embedding a newline could otherwise forge what looks like a second, standalone
    # entry in a printed report or table (see cli.py's regression test for the end-to-end case).
    candidate = Candidate(
        candidate_id="id-1", email=None, phone=None, name="Fake\nFORGED ROW: Evil"
    )

    assert "\n" not in candidate_label(candidate)
