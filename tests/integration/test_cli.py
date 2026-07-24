"""End-to-end tests for the command-line bridge (src/hr_digital_employee/cli.py)."""

from __future__ import annotations

import io
import sqlite3
import sys
from pathlib import Path

import pytest

from hr_digital_employee.cli import _print_report, build_argument_parser, main, run
from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog
from hr_digital_employee.intake_extraction.manual_review_queue import ManualReviewQueue
from hr_digital_employee.scoring_engine.jrp_config import load_jrp_from_yaml
from hr_digital_employee.scoring_engine.models import (
    JRP,
    Dimension,
    MatchingCurve,
    Score,
    Tier,
    WeightedCriterion,
    WeightTemplate,
)

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


def test_main_reports_a_clean_error_for_a_nonexistent_resumes_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Regression: --resumes was never validated as an existing directory -- LocalFolderChannel
    # Adapter treats a missing folder the same as an empty one, so a typo'd path silently produced
    # a clean-looking but completely empty report ("Scored: 0   Routed to manual review: 0")
    # instead of any error, indistinguishable from "this folder genuinely has no resumes yet".
    jrp_path = _write_jrp(tmp_path)

    exit_code = main(
        ["--resumes", str(tmp_path / "does-not-exist"), "--jrp", str(jrp_path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "--resumes path not found or not a directory" in captured.err


def test_main_reports_a_clean_error_when_resumes_points_at_a_file_not_a_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Same gap, a different real-world trigger: accidentally passing the JRP path (or any other
    # file) to --resumes instead of a folder.
    jrp_path = _write_jrp(tmp_path)

    exit_code = main(["--resumes", str(jrp_path), "--jrp", str(jrp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "--resumes path not found or not a directory" in captured.err


def test_main_reports_a_clean_error_when_audit_db_path_is_not_a_sqlite_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Regression: an --audit-db path that exists but isn't a SQLite file raised an uncaught
    # sqlite3.DatabaseError -- a raw traceback instead of an actionable message.
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    jrp_path = _write_jrp(tmp_path)
    not_a_db = tmp_path / "not_a_db.db"
    not_a_db.write_text("this is not a sqlite file", encoding="utf-8")

    exit_code = main(
        ["--resumes", str(resumes_dir), "--jrp", str(jrp_path), "--audit-db", str(not_a_db)]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error using --audit-db" in captured.err


def test_main_reports_a_clean_error_when_audit_db_has_an_incompatible_schema(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Regression: an --audit-db pointing at a real SQLite file whose audit_events table doesn't
    # match this schema didn't fail at construction (CREATE TABLE IF NOT EXISTS silently no-ops
    # against the existing table) -- it raised an uncaught sqlite3.OperationalError only later,
    # on the first actual record() call, mid-pipeline, with no report ever printed.
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "candidate.pdf").write_bytes(STRONG_RESUME)
    jrp_path = _write_jrp(tmp_path)
    incompatible_db = tmp_path / "incompatible.db"
    connection = sqlite3.connect(str(incompatible_db))
    connection.execute(
        "CREATE TABLE audit_events (id INTEGER PRIMARY KEY, actor TEXT, entity_ref TEXT, "
        "action TEXT, reason TEXT, timestamp TEXT)"  # missing the "version" column
    )
    connection.commit()
    connection.close()

    exit_code = main(
        ["--resumes", str(resumes_dir), "--jrp", str(jrp_path), "--audit-db", str(incompatible_db)]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error using --audit-db" in captured.err


def test_a_candidate_label_containing_a_newline_cannot_forge_an_extra_report_row(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Regression: the candidate label (ultimately from untrusted submission data -- a message
    # envelope's display name/email, once a real Email/Teams adapter is built) was printed
    # verbatim, so a label containing a newline plus text shaped like a table row rendered as what
    # looked like a second, standalone entry in the report.
    jrp = JRP(
        jrp_id="role-1",
        role_name="Backend Engineer",
        version=1,
        weight_template=WeightTemplate.GENERAL,
        weighted_criteria=(
            WeightedCriterion(
                dimension=Dimension.MANDATORY_SKILLS,
                weight=100.0,
                curve=MatchingCurve.LINEAR,
                required_skills=("Python",),
            ),
        ),
    )
    score = Score(
        jrp_id="role-1",
        jrp_version=1,
        scoring_engine_version="v1",
        parser_version="v1",
        total_score=90.0,
        tier=Tier.HIGH_MATCH,
        passed_must_have=True,
        failed_must_have_labels=(),
        breakdown=(),
    )
    forged_label = "FakeCo\nFORGED ROW  999.0  high_match  pass"

    _print_report(jrp, [(forged_label, score)], ManualReviewQueue())

    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert not any(line.startswith("FORGED ROW") for line in lines)
    assert any("FakeCo FORGED ROW" in line for line in lines)


def test_a_candidate_label_containing_an_ansi_escape_sequence_is_stripped(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Regression (round 6): only "\n"/"\r" were stripped from a printed label -- a raw ANSI
    # escape sequence (ESC, \x1b -- e.g. a screen-clear plus fake colored "success" text) survived
    # unstripped, letting untrusted candidate-name data spoof console output.
    jrp = JRP(
        jrp_id="role-1",
        role_name="Backend Engineer",
        version=1,
        weight_template=WeightTemplate.GENERAL,
        weighted_criteria=(
            WeightedCriterion(
                dimension=Dimension.MANDATORY_SKILLS,
                weight=100.0,
                curve=MatchingCurve.LINEAR,
                required_skills=("Python",),
            ),
        ),
    )
    score = Score(
        jrp_id="role-1",
        jrp_version=1,
        scoring_engine_version="v1",
        parser_version="v1",
        total_score=90.0,
        tier=Tier.HIGH_MATCH,
        passed_must_have=True,
        failed_must_have_labels=(),
        breakdown=(),
    )
    spoofed_label = "\x1b[2J\x1b[H\x1b[32mFAKE: All candidates passed with 100.00\x1b[0m"

    _print_report(jrp, [(spoofed_label, score)], ManualReviewQueue())

    captured = capsys.readouterr()
    assert "\x1b" not in captured.out
    assert "FAKE: All candidates passed with 100.00" in captured.out


def test_a_candidate_name_with_unencodable_characters_does_not_crash_the_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression: a CJK or emoji candidate name raised an uncaught `UnicodeEncodeError` under a
    # legacy console encoding (e.g. Windows cp1252), aborting the whole report mid-batch.
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "candidate.pdf").write_bytes(STRONG_RESUME)
    jrp_path = _write_jrp(tmp_path)

    fake_stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    exit_code = main(["--resumes", str(resumes_dir), "--jrp", str(jrp_path)])

    assert exit_code == 0


def test_argument_parser_requires_resumes_and_jrp() -> None:
    parser = build_argument_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])
