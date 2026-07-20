# Assumptions

Per `md/prompt.md` §3 (stub-and-document): every place a real-world/vendor decision is still open,
the code below builds a working interface + local stub instead of guessing or stalling. Each entry
here says what was built, what a real implementation must satisfy, and why.

## Channel intake (Email/Teams/WhatsApp connectors)

**Status:** Stubbed — pending human decision (see `md/progress.md` §2a)
**What was built:** `ChannelAdapter` protocol (`intake_extraction/channel_adapters.py`) with one
method, `fetch_new_submissions() -> list[RawSubmission]`. `LocalFolderChannelAdapter` implements it
by reading `*.pdf` files from a local folder.
**What a real implementation must satisfy:** same protocol — return `RawSubmission` objects for
each new item since the last fetch, tagged with the correct `SubmissionChannel`. A real Email
adapter would poll/webhook a mailbox; a real Teams adapter would use Microsoft Graph; WhatsApp is
additionally gated behind Business API verification (see `md/requirement.md` §7.2) before it can
exist at all.
**Why this default:** keeps Module 1 fully testable without committing to Microsoft Graph, IMAP, or
any specific vendor SDK.

## PDF byte-to-text extraction

**Status:** Resolved — build-vs-buy decision made (see `md/progress.md` §2a, `design.md` §10.6)
**What was built:** `extract_text()` (`intake_extraction/pdf_text.py`) uses `pypdf` to read a real
PDF's text layer. Bytes that don't start with the `%PDF-` header are passed through as
already-plain-text, which keeps non-PDF test fixtures (and any future plain-text channel) working
without wrapping every input in a real PDF container. Returns `None` (routes to manual review,
FR-4) for encrypted PDFs, corrupted/unreadable PDFs, and PDFs with no extractable text layer at
all (e.g. a scanned/image-only page) — this module does not attempt OCR.
**What a real implementation must satisfy:** already satisfied for text-layer PDFs; OCR for
scanned/image-only resumes is out of scope here and still routes to manual review, which is
consistent with FR-4's "unparseable → manual queue" rule rather than a gap.
**Why this choice:** `pypdf` handles the common case (a text-based PDF export) with no vendor
dependency or network call, and the manual-review fallback covers the scanned/OCR case FR-4
already requires human handling for.

## Structured extraction (Skills/Projects/Experience/Education splitting)

**Status:** Stubbed — pending human decision (see `md/progress.md` §2a)
**What was built:** `ExtractionService` (`intake_extraction/extraction.py`) — a heuristic,
section-header-regex-based splitter that extracts the four pillars (Skills, Projects, Experience,
Education) with a length-based confidence heuristic (long section = 0.95, short = 0.5, missing =
0.0/`UNVERIFIED`). This operates on the plain text `pdf_text.py` produces, so PDF parsing itself
is real now — this heuristic section-splitter is the remaining stub.
**What a real implementation must satisfy:** same return type, `ExtractedResume` with per-field
`ExtractedField[T]` (value, confidence, status). Must hit the ≥95% field-level accuracy bar against
the ≥200-resume annotated validation set (`requirement.md` NFR-1) before automatic gating is
enabled — this stub does **not** meet that bar and must not be used to drive real hiring decisions.
**Why this default:** whether to replace this regex heuristic with a managed document-intelligence
API or a custom NLP model is still unresolved; a working stub lets every downstream module (dedup,
gateway, eventually Module 2's scoring) be built and tested against a real interface now.

## Malware/sandbox scanning

**Status:** Stubbed — not yet implemented
**What was built:** nothing yet — `IngestionGateway` does not currently call a malware scanner
before injection screening.
**What a real implementation must satisfy:** SOP 5.1 requires attachments to be scanned in an
isolated environment before parsing; suspected malicious files must be quarantined and reported to
HR, never enter the scoring pipeline.
**Why flagged rather than stubbed:** this needs an actual sandboxing environment/service, which
isn't meaningfully stubbable as pure Python logic the way a data adapter is. Left as an explicit gap
for the next build pass rather than faked.

## Name-similarity matching (identity dedup)

**Status:** Stubbed — heuristic only
**What was built:** `_name_similarity()` in `intake_extraction/dedup.py` — token-overlap ratio
between two names (Jaccard-like on whitespace-split tokens). Not a real fuzzy-matching library.
**What a real implementation must satisfy:** SOP 2.1.3's "name-plus-resume similarity" — likely
wants a proper fuzzy-string library (e.g., edit distance) plus resume-content similarity, not just
name tokens.
**Why this default:** keeps `IdentityDedupService` fully testable and demonstrates the
merge/ambiguous/new three-way outcome without pulling in a fuzzy-matching dependency before that
choice is made deliberately.

## Audit log persistence

**Status:** Stubbed — pending human decision (data residency, `md/progress.md` §2a)
**What was built:** `InMemoryAuditLog` (`governance_audit/audit_log.py`) implementing the
`AuditLog` protocol — events live in a Python list, lost on process exit.
**What a real implementation must satisfy:** durable, append-only storage, retained independently
of application data per SOP 4.3's layered retention (identifiable data erasable; pseudonymized
decision logs retained separately for their own period).
**Why this default:** lets every other module (Module 1's gateway, and eventually all others) log
through the real `AuditLog` protocol now, without picking a database or region ahead of that
decision being made.

## Manual-review queue persistence

**Status:** Stubbed — in-memory only
**What was built:** `ManualReviewQueue` (`intake_extraction/manual_review_queue.py`) — a plain
in-memory list.
**What a real implementation must satisfy:** persistence across process restarts, plus the SLA
monitoring described in `md/modules/module-7-governance-audit.md` (queue depth, 1-business-day
alerting to the named owner — who is also not yet assigned, see `md/progress.md` §2b).
**Why this default:** keeps Module 1's gateway testable in isolation; SLA monitoring itself belongs
to Module 7 and is not yet built (see "Not yet built" below).

## What this draft does NOT cover yet

This is a rough first draft of Wave 1 only (Module 1: Intake & Extraction, and the minimum of
Module 7: Governance & Audit needed for Module 1 to log through it). **Not yet built:** manual-
review SLA monitoring/alerting, incident routing, weekly operational review, Talent Pool Store,
Candidate Feedback storage, and Modules 2 through 6 entirely (empty placeholder packages only, per
`md/prompt.md` §5's repository layout). See `md/progress.md` for the authoritative checklist.
