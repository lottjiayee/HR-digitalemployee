"""Tests for the local-folder stub channel adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from hr_digital_employee.intake_extraction.channel_adapters import (
    LocalFolderChannelAdapter,
    UploadedFilesChannelAdapter,
)
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


def test_docx_rtf_and_extensionless_files_are_ignored_by_the_folder_scan(tmp_path: Path) -> None:
    # Locks in _SUPPORTED_EXTENSIONS' documented scope: these formats have no text-layer/OCR path
    # in pdf_text.py, so this stub deliberately never picks them up -- unlike a real Email/Teams
    # connector (which receives attachments by content, not filename), a real resume in one of
    # these formats is silently never processed by this local-folder stand-in at all.
    (tmp_path / "resume.docx").write_bytes(b"PK\x03\x04fake-docx-bytes")
    (tmp_path / "resume.rtf").write_bytes(rb"{\rtf1 fake rtf}")
    (tmp_path / "resume_no_extension").write_bytes(b"Skills:\nPython\n")
    (tmp_path / "resume.pdf").write_bytes(b"Skills:\nSQL\n")

    adapter = LocalFolderChannelAdapter(tmp_path)
    submissions = adapter.fetch_new_submissions()

    assert {s.file_bytes for s in submissions} == {b"Skills:\nSQL\n"}


def test_a_unicode_or_emoji_filename_is_read_correctly(tmp_path: Path) -> None:
    (tmp_path / "张伟_简历.pdf").write_bytes(b"Skills:\nPython\n")
    (tmp_path / "resume_\U0001f600.pdf").write_bytes(b"Skills:\nSQL\n")

    adapter = LocalFolderChannelAdapter(tmp_path)
    submissions = adapter.fetch_new_submissions()

    names = {s.candidate_name for s in submissions}
    assert names == {"张伟_简历", "resume_\U0001f600"}
    assert {s.file_bytes for s in submissions} == {b"Skills:\nPython\n", b"Skills:\nSQL\n"}


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


def test_the_whole_folder_vanishing_between_the_exists_check_and_listing_is_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression: the same class of TOCTOU race as above, one level up -- `exists()` passing
    # doesn't guarantee `iterdir()` will succeed a moment later (a concurrent cleanup job, an
    # unmounted network share). Only the per-file read was ever guarded; the folder-level listing
    # itself raised an uncaught OSError out of fetch_new_submissions().
    (tmp_path / "resume1.pdf").write_bytes(b"Skills:\nPython\n")
    adapter = LocalFolderChannelAdapter(tmp_path)

    def _vanished_iterdir(self: Path) -> object:
        raise FileNotFoundError(f"{self} vanished")

    monkeypatch.setattr(Path, "iterdir", _vanished_iterdir)

    assert adapter.fetch_new_submissions() == []


def test_uploaded_files_adapter_returns_one_submission_per_upload() -> None:
    adapter = UploadedFilesChannelAdapter(
        [
            ("resume1.pdf", b"Skills:\nPython\n"),
            ("resume2.jpg", b"fake-jpeg-bytes"),
        ]
    )

    submissions = adapter.fetch_new_submissions()

    assert {s.file_bytes for s in submissions} == {b"Skills:\nPython\n", b"fake-jpeg-bytes"}


def test_uploaded_files_adapter_candidate_name_falls_back_to_the_filename_stem() -> None:
    adapter = UploadedFilesChannelAdapter([("jane_doe_resume.pdf", b"Skills:\nPython\n")])

    submissions = adapter.fetch_new_submissions()

    assert submissions[0].candidate_name == "jane_doe_resume"
    assert submissions[0].candidate_email is None
    assert submissions[0].candidate_phone is None


def test_uploaded_files_adapter_uses_the_given_channel() -> None:
    adapter = UploadedFilesChannelAdapter(
        [("resume1.pdf", b"Skills:\nPython\n")], channel=SubmissionChannel.WHATSAPP
    )

    submissions = adapter.fetch_new_submissions()

    assert submissions[0].channel is SubmissionChannel.WHATSAPP


def test_uploaded_files_adapter_handles_an_empty_upload_list() -> None:
    adapter = UploadedFilesChannelAdapter([])

    assert adapter.fetch_new_submissions() == []


def test_uploaded_files_adapter_returns_the_same_uploads_on_every_fetch_call() -> None:
    # Unlike LocalFolderChannelAdapter (which tracks "already seen" paths across calls, mirroring a
    # real Email/Teams cursor), UploadedFilesChannelAdapter has no such cursor -- its docstring says
    # each call returns the same list, since callers are expected to construct a fresh adapter per
    # batch rather than reuse one across multiple upload rounds.
    adapter = UploadedFilesChannelAdapter([("resume1.pdf", b"Skills:\nPython\n")])

    first = adapter.fetch_new_submissions()
    second = adapter.fetch_new_submissions()

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].file_bytes == second[0].file_bytes == b"Skills:\nPython\n"
