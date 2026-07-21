"""Tests for the persistent, append-only extracted-text log (module-1 design.md §3.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from hr_digital_employee.intake_extraction.models import RawSubmission, SubmissionChannel
from hr_digital_employee.intake_extraction.text_extraction_log import TextExtractionLog


def _submission(email: str | None = "a@example.com") -> RawSubmission:
    return RawSubmission(
        channel=SubmissionChannel.EMAIL,
        candidate_email=email,
        candidate_phone=None,
        candidate_name=None,
        file_bytes=b"",
        received_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_append_creates_file_and_writes_the_extracted_text(tmp_path: Path) -> None:
    log_path = tmp_path / "extracted_text.txt"
    log = TextExtractionLog(log_path)

    log.append(_submission(), "Skills:\nPython, SQL")

    content = log_path.read_text(encoding="utf-8")
    assert "Skills:\nPython, SQL" in content
    assert "a@example.com" in content
    assert "email" in content
    assert "2026-01-01" in content


def test_append_grows_the_file_instead_of_overwriting_it(tmp_path: Path) -> None:
    log_path = tmp_path / "extracted_text.txt"
    log = TextExtractionLog(log_path)

    log.append(_submission(email="first@example.com"), "First resume text")
    log.append(_submission(email="second@example.com"), "Second resume text")

    content = log_path.read_text(encoding="utf-8")
    assert "First resume text" in content
    assert "Second resume text" in content
    assert "first@example.com" in content
    assert "second@example.com" in content


def test_missing_identity_falls_back_to_unknown(tmp_path: Path) -> None:
    log_path = tmp_path / "extracted_text.txt"
    log = TextExtractionLog(log_path)

    log.append(_submission(email=None), "Some text")

    assert "candidate=unknown" in log_path.read_text(encoding="utf-8")
