"""Channel adapters for resume intake (SOP 1.2, 2.1.4).

Real Email/Teams/WhatsApp integrations are an open decision (md/progress.md §2a) -- this module
defines the interface every adapter must satisfy and ships a local-filesystem stub so the rest of
the pipeline is fully testable without a real vendor integration. See ASSUMPTIONS.md for what a
real adapter must satisfy.

`UploadedFilesChannelAdapter` accepts in-memory (filename, bytes) pairs -- e.g. from Streamlit's
`st.file_uploader` -- so the dashboard can feed browser-uploaded files directly into the pipeline
without writing anything to disk.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from hr_digital_employee.intake_extraction.models import RawSubmission, SubmissionChannel

_SUPPORTED_EXTENSIONS = frozenset({".pdf", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"})
"""Extensions this stub picks up -- mirrors what pdf_text.extract_text() can actually read
(PDF text layer or OCR'd image); a real Email/Teams connector receives attachments by content,
not by filename extension, so this is purely an artifact of the local-folder stub.

Matched via `Path.suffix.lower()` rather than a `Path.glob("*.pdf")`-style pattern deliberately --
glob's case sensitivity follows the OS (case-insensitive on Windows, case-sensitive on the Linux
this would actually deploy to), so a real-world `Resume.PDF`/`SCAN0001.PDF` would silently never be
picked up at all -- not read, not queued to manual review, not logged anywhere -- on a case-
sensitive filesystem with the glob-pattern approach."""


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
        try:
            # The folder can vanish between the `exists()` check above and this listing (a
            # concurrent cleanup job, an unmounted network share) -- treat that the same as it not
            # existing at all (no submissions this cycle) rather than an uncaught OSError.
            matches = [
                path
                for path in self._folder.iterdir()
                if path.suffix.lower() in _SUPPORTED_EXTENSIONS
            ]
        except OSError:
            return submissions
        new_paths = sorted(path for path in matches if path not in self._seen_paths)
        for file_path in new_paths:
            self._seen_paths.add(file_path)
            try:
                # A file listed a moment ago can vanish before it's read (a concurrent cleanup
                # job, a flaky network share, another process moving already-processed files) --
                # skip just this one file rather than losing the whole fetch to an uncaught
                # FileNotFoundError (it was already added to _seen_paths above, so a permanently
                # gone file isn't retried forever; one that reappears will look "new" again since
                # nothing else observed it).
                file_bytes = file_path.read_bytes()
            except OSError:
                continue
            submissions.append(
                RawSubmission(
                    channel=self._channel,
                    candidate_email=None,
                    candidate_phone=None,
                    # A real Email/Teams adapter gets the candidate's name from the message
                    # envelope; this stub has no envelope, so it falls back to the filename (minus
                    # extension) as the closest available human-readable identifier -- otherwise
                    # every submission is indistinguishable except by its generated candidate_id.
                    candidate_name=file_path.stem,
                    file_bytes=file_bytes,
                    received_at=datetime.now(UTC),
                )
            )
        return submissions


class UploadedFilesChannelAdapter:
    """In-memory adapter: wraps a list of (filename, file_bytes) pairs as resume submissions.

    Intended for the Streamlit dashboard's `st.file_uploader` widget -- the browser sends bytes
    directly, so no local folder or disk write is needed. Each call to `fetch_new_submissions`
    returns the same list (callers are expected to construct a fresh adapter per batch).
    """

    def __init__(
        self,
        uploads: list[tuple[str, bytes]],
        channel: SubmissionChannel = SubmissionChannel.EMAIL,
    ) -> None:
        self._uploads = uploads
        self._channel = channel

    def fetch_new_submissions(self) -> list[RawSubmission]:
        """Return one RawSubmission per uploaded file. The filename stem (minus extension) is used
        as the candidate name, mirroring `LocalFolderChannelAdapter`'s fallback behaviour."""
        return [
            RawSubmission(
                channel=self._channel,
                candidate_email=None,
                candidate_phone=None,
                # Strip extension for a cleaner display label, same as LocalFolderChannelAdapter.
                candidate_name=Path(filename).stem,
                file_bytes=file_bytes,
                received_at=datetime.now(UTC),
            )
            for filename, file_bytes in self._uploads
        ]
