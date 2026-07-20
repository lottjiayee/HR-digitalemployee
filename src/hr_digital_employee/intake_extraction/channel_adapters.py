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

    def fetch_new_submissions(self) -> list[RawSubmission]:
        submissions: list[RawSubmission] = []
        if not self._folder.exists():
            return submissions
        for file_path in sorted(self._folder.glob("*.pdf")):
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
