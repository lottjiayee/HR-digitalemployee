"""Channel adapters for resume intake (SOP 1.2, 2.1.4).

Real Email/Teams/WhatsApp integrations are an open decision (md/progress.md §2a) -- this module
defines the interface every adapter must satisfy and ships a local-filesystem stub so the rest of
the pipeline is fully testable without a real vendor integration. See ASSUMPTIONS.md for what a
real adapter must satisfy.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from hr_digital_employee.intake_extraction.models import RawSubmission, SubmissionChannel

_SUPPORTED_FILE_GLOBS = ("*.pdf", "*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp", "*.webp")
"""Extensions this stub picks up -- mirrors what pdf_text.extract_text() can actually read
(PDF text layer or OCR'd image); a real Email/Teams connector receives attachments by content,
not by filename extension, so this glob is purely an artifact of the local-folder stub."""


class ChannelAdapter(Protocol):
    """A source of new resume submissions."""

    def fetch_new_submissions(self) -> list[RawSubmission]: ...


class LocalFolderChannelAdapter:
    """Stub adapter: reads files from a local folder as if they were emailed/messaged in.

    Stands in for a real Email/Microsoft Graph/Teams connector (see ASSUMPTIONS.md).
    """

    def __init__(self, folder: Path, channel: SubmissionChannel = SubmissionChannel.EMAIL) -> None:
        self._folder = folder
        self._channel = channel
        self._seen_paths: set[Path] = set()

    def fetch_new_submissions(self) -> list[RawSubmission]:
        """Return submissions for files not already returned by a previous call on this adapter
        instance -- a real Email/Teams adapter tracks "since the last fetch" via a cursor/message
        id; this stub tracks it as an in-memory set of paths already seen (ASSUMPTIONS.md)."""
        submissions: list[RawSubmission] = []
        if not self._folder.exists():
            return submissions
        matches = (path for pattern in _SUPPORTED_FILE_GLOBS for path in self._folder.glob(pattern))
        new_paths = sorted(path for path in matches if path not in self._seen_paths)
        for file_path in new_paths:
            self._seen_paths.add(file_path)
            submissions.append(
                RawSubmission(
                    channel=self._channel,
                    candidate_email=None,
                    candidate_phone=None,
                    candidate_name=None,
                    file_bytes=file_path.read_bytes(),
                    received_at=datetime.now(UTC),
                )
            )
        return submissions
