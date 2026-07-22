"""End-to-end tests for the command-line bridge (src/hr_digital_employee/cli.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hr_digital_employee.cli import build_argument_parser, main, run
from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog
from hr_digital_employee.scoring_engine.jrp_config import load_jrp_from_yaml
from hr_digital_employee.scoring_engine.models import Tier

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

# LocalFolderChannelAdapter globs by extension (*.pdf, image types) -- pdf_text.py then dispatches
# on content, not extension, so plain text saved with a .pdf name is the established fixture
# pattern for this adapter (see tests/intake_extraction/test_channel_adapters.py).
STRONG_RESUME = (
    b"Skills:\nPython\nSQL\n\n"
    b"Projects:\nBuilt a data pipeline\nLed a small team\n\n"
    b"Working Experience:\n5 years at TechCorp as a backend engineer\n\n"
    b"Education:\nBachelor of Computer Science\n"
)

THIN_RESUME = b"Skills:\nP\n\nWorking Experience:\nN/A\n\nEducation:\nBSc\n"


def _write_jrp(tmp_path: Path) -> Path:
    jrp_path = tmp_path / "backend-engineer.yaml"
    jrp_path.write_text(JRP_CONFIG, encoding="utf-8")
    return jrp_path


def test_run_scores_a_resume_folder_against_a_jrp(tmp_path: Path) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "candidate.pdf").write_bytes(STRONG_RESUME)
    jrp = load_jrp_from_yaml(_write_jrp(tmp_path))

    results, manual_review_queue = run(resumes_dir, jrp, InMemoryAuditLog())

    assert len(results) == 1
    _label, score = results[0]
    assert score.total_score == 100.0
    assert score.tier is Tier.HIGH_MATCH
    assert len(manual_review_queue) == 0


def test_run_routes_a_thin_resume_to_manual_review_not_a_score(tmp_path: Path) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "candidate.pdf").write_bytes(THIN_RESUME)
    jrp = load_jrp_from_yaml(_write_jrp(tmp_path))

    results, manual_review_queue = run(resumes_dir, jrp, InMemoryAuditLog())

    assert results == []
    assert len(manual_review_queue) == 1


def test_run_sorts_results_by_score_descending(tmp_path: Path) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "strong.pdf").write_bytes(STRONG_RESUME)
    weaker_resume = (
        b"Skills:\nPython\nSQL\n\nProjects:\nOne project\n\n"
        b"Working Experience:\n2 years at StartCo\n\nEducation:\nBachelor of Arts\n"
    )
    (resumes_dir / "weaker.pdf").write_bytes(weaker_resume)
    jrp = load_jrp_from_yaml(_write_jrp(tmp_path))

    results, _queue = run(resumes_dir, jrp, InMemoryAuditLog())

    assert len(results) == 2
    assert results[0][1].total_score >= results[1][1].total_score


def test_main_prints_a_report_and_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "candidate.pdf").write_bytes(STRONG_RESUME)
    jrp_path = _write_jrp(tmp_path)

    exit_code = main(["--resumes", str(resumes_dir), "--jrp", str(jrp_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Backend Engineer" in captured.out
    assert "100.0" in captured.out


def test_main_persists_the_audit_log_to_a_sqlite_file_when_requested(tmp_path: Path) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "candidate.pdf").write_bytes(STRONG_RESUME)
    jrp_path = _write_jrp(tmp_path)
    audit_db = tmp_path / "audit.db"

    exit_code = main(
        ["--resumes", str(resumes_dir), "--jrp", str(jrp_path), "--audit-db", str(audit_db)]
    )

    assert exit_code == 0
    assert audit_db.exists()


def test_main_returns_nonzero_and_prints_an_error_for_an_invalid_jrp_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    bad_jrp_path = tmp_path / "bad.yaml"
    bad_jrp_path.write_text("weight_template: nonsense\n", encoding="utf-8")

    exit_code = main(["--resumes", str(resumes_dir), "--jrp", str(bad_jrp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error loading JRP config" in captured.err


def test_argument_parser_requires_resumes_and_jrp() -> None:
    parser = build_argument_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])
