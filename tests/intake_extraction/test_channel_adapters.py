"""Tests for the local-folder stub channel adapter."""

from __future__ import annotations

from pathlib import Path

from hr_digital_employee.intake_extraction.channel_adapters import LocalFolderChannelAdapter
from hr_digital_employee.intake_extraction.models import SubmissionChannel


def test_reads_pdf_files_from_folder(tmp_path: Path) -> None:
    (tmp_path / "resume1.pdf").write_bytes(b"Skills:\nPython\n")
    (tmp_path / "not_a_resume.txt").write_bytes(b"ignored")

    adapter = LocalFolderChannelAdapter(tmp_path, channel=SubmissionChannel.TEAMS)
    submissions = adapter.fetch_new_submissions()

    assert len(submissions) == 1
    assert submissions[0].channel is SubmissionChannel.TEAMS
    assert submissions[0].file_bytes == b"Skills:\nPython\n"


def test_reads_image_files_from_folder(tmp_path: Path) -> None:
    (tmp_path / "resume1.jpg").write_bytes(b"fake-jpeg-bytes")
    (tmp_path / "resume2.png").write_bytes(b"fake-png-bytes")
    (tmp_path / "not_a_resume.txt").write_bytes(b"ignored")

    adapter = LocalFolderChannelAdapter(tmp_path)
    submissions = adapter.fetch_new_submissions()

    assert {s.file_bytes for s in submissions} == {b"fake-jpeg-bytes", b"fake-png-bytes"}


def test_candidate_name_falls_back_to_the_filename_stem(tmp_path: Path) -> None:
    (tmp_path / "jane_doe_resume.pdf").write_bytes(b"Skills:\nPython\n")

    adapter = LocalFolderChannelAdapter(tmp_path)
    submissions = adapter.fetch_new_submissions()

    assert submissions[0].candidate_name == "jane_doe_resume"
    assert submissions[0].candidate_email is None
    assert submissions[0].candidate_phone is None


def test_missing_folder_returns_empty_list(tmp_path: Path) -> None:
    adapter = LocalFolderChannelAdapter(tmp_path / "does_not_exist")

    assert adapter.fetch_new_submissions() == []


def test_a_file_already_returned_is_not_returned_again_on_the_next_fetch(tmp_path: Path) -> None:
    (tmp_path / "resume1.pdf").write_bytes(b"Skills:\nPython\n")
    adapter = LocalFolderChannelAdapter(tmp_path)

    first = adapter.fetch_new_submissions()
    (tmp_path / "resume2.pdf").write_bytes(b"Skills:\nSQL\n")
    second = adapter.fetch_new_submissions()

    assert len(first) == 1
    assert len(second) == 1
    assert second[0].file_bytes == b"Skills:\nSQL\n"
