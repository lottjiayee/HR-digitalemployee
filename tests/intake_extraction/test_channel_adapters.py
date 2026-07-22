"""Tests for the local-folder stub channel adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_uppercase_and_mixed_case_extensions_are_still_picked_up(tmp_path: Path) -> None:
    # Regression: matching via Path.glob("*.pdf")-style patterns follows the OS's case
    # sensitivity (case-insensitive on Windows, case-sensitive on the Linux this would actually
    # deploy to) -- a real-world "Resume.PDF" or scanner output like "SCAN0001.PDF" would silently
    # never be picked up at all on a case-sensitive filesystem: not read, not queued to manual
    # review, not logged anywhere.
    (tmp_path / "Resume.PDF").write_bytes(b"Skills:\nPython\n")
    (tmp_path / "SCAN0001.JPG").write_bytes(b"fake-jpeg-bytes")

    adapter = LocalFolderChannelAdapter(tmp_path)
    submissions = adapter.fetch_new_submissions()

    assert {s.file_bytes for s in submissions} == {b"Skills:\nPython\n", b"fake-jpeg-bytes"}


def test_a_file_deleted_between_listing_and_reading_is_skipped_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression: a TOCTOU race between listing the folder and reading each matched file (a
    # concurrent cleanup job, a flaky network share, another process moving already-processed
    # files) used to raise an uncaught FileNotFoundError out of fetch_new_submissions(), losing
    # every other file in that same fetch, not just the one that vanished. Simulated by making
    # read_bytes() fail for one specific already-listed file, the same shape as the real race
    # (present during iterdir(), gone by the time it's actually read).
    (tmp_path / "resume1.pdf").write_bytes(b"Skills:\nPython\n")
    (tmp_path / "resume2.pdf").write_bytes(b"Skills:\nSQL\n")
    adapter = LocalFolderChannelAdapter(tmp_path)
    original_read_bytes = Path.read_bytes

    def _flaky_read_bytes(self: Path) -> bytes:
        if self.name == "resume1.pdf":
            raise FileNotFoundError(f"{self} vanished")
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", _flaky_read_bytes)

    submissions = adapter.fetch_new_submissions()

    assert len(submissions) == 1
    assert submissions[0].file_bytes == b"Skills:\nSQL\n"
