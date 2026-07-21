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
**Fixed 2026-07-21:** `LocalFolderChannelAdapter.fetch_new_submissions()` re-returned every file in
the folder on every call, contradicting this section's own contract ("each new item since the last
fetch") -- calling `IngestionGateway.run_once()` on a loop (its only realistic usage) would
reprocess the same resumes forever. Now tracks already-returned paths in memory per adapter
instance, matching the cursor-like semantics a real Email/Teams adapter would use.

## PDF byte-to-text extraction

**Status:** Resolved — build-vs-buy decision made (see `md/progress.md` §2a, `design.md` §10.6)
**What was built:** `extract_text()` (`intake_extraction/pdf_text.py`) uses `pypdf` to read a real
PDF's text layer. Bytes that don't start with the `%PDF-` header are passed through as
already-plain-text-or-image, which keeps non-PDF test fixtures (and any future plain-text channel)
working without wrapping every input in a real PDF container. Returns `None` (routes to manual
review, FR-4) for encrypted PDFs, corrupted/unreadable PDFs, and PDFs with no extractable text
layer at all (e.g. a scanned/image-only page) — **this module does not rasterize a PDF page**, so
a scanned/image-only PDF is still unparseable regardless of the OCR capability described below
(consistent with `test.md` T1.6's explicit "non-OCR" wording for that specific case).
**What a real implementation must satisfy:** already satisfied for text-layer PDFs; rasterizing a
scanned/image-only PDF page to run it through OCR is out of scope here and still routes to manual
review, which is consistent with FR-4's "unparseable → manual queue" rule rather than a gap.
**Why this choice:** `pypdf` handles the common case (a text-based PDF export) with no vendor
dependency or network call, and the manual-review fallback covers the scanned/OCR case FR-4
already requires human handling for.
**Fixed 2026-07-20:** the non-PDF fallback originally decoded bytes as UTF-8 with
`errors="replace"`, so an arbitrary binary file (e.g. an image submitted with a `.pdf` extension)
silently decoded into replacement-character garbage instead of being rejected — it then sailed
through extraction as an empty-but-accepted candidate record with no manual-review flag at all.
The fallback now decodes strictly and returns `None` (→ manual review, FR-4) on
`UnicodeDecodeError`. Found by manually running a real non-PDF file through the pipeline; see
`tests/intake_extraction/test_pdf_text.py::test_non_pdf_binary_that_is_not_valid_text_is_unparseable`.

## Image OCR (a resume submitted directly as a JPEG/PNG/GIF/BMP/WEBP)

**Status:** Resolved on the free/offline side only — cloud OCR remains a live alternative
(`md/progress.md` §2a, `design.md` §10.6)
**What was built:** `intake_extraction/ocr.py` — `is_image()` detects a raster image by magic
bytes, `extract_text()` runs it through Tesseract via `pytesseract` (added as a regular
dependency, alongside `pytesseract`'s required system binary — see below). Wired into
`pdf_text.extract_text()`'s dispatch, and the `LocalFolderChannelAdapter` stub now also globs
image extensions, not just `*.pdf`. Returns `None` (routes to manual review, FR-4) if the image
can't be decoded or Tesseract can't be found.
**System dependency:** this is not a pure-Python `pip install` — it requires the Tesseract binary
installed on the machine (here: `winget install --id UB-Mannheim.TesseractOCR`). Because the
winget installer doesn't reliably land on `PATH` in an already-open shell, `ocr.py` also tries the
package's standard Windows install locations as a fallback (`_WINDOWS_FALLBACK_TESSERACT_PATHS`).
Test coverage that actually invokes OCR is skipped (`pytest.mark.skipif`, via
`ocr.tesseract_available()`) on any machine without the binary, so the mandatory pytest gate still
passes without it — only `is_image()`'s pure byte-sniffing is unconditionally tested.
**Accuracy tradeoff (observed, not theoretical):** running Tesseract against a real-world resume
template (icons, a colored sidebar, a timeline layout) produced meaningfully corrupted text —
"Work History" read back as "work tistory" (missing the new `work\s+history` alias below), several
lines fused with adjacent icon glyphs into nonsense tokens, and one section's content spilled into
the wrong field as a result. A clean single-column, plain-text-on-white-background resume OCRs
close to perfectly by comparison (see `tests/intake_extraction/test_ocr.py`). This is the accuracy
cost of the free/offline choice versus a managed cloud document-intelligence API (Azure AI Document
Intelligence, AWS Textract) — those are trained specifically on document layouts and would likely
handle icons/columns/sidebars far better, at the cost of an account, API key, and per-page cost
above the free tier.
**Why this default:** unblocks local testing/demoing of image-format resumes with no account,
API key, or network dependency; revisit in favor of a cloud OCR provider once real accuracy
requirements (NFR-1's ≥95% bar) are measured against real resume samples, not just this one
template.

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
**Fixed 2026-07-20:** the experience-section header regex only matched the literal word
"experience" (optionally prefixed with "work"/"working"). A real-world resume using the equally
common heading "Work History" or "Employment History" found no match, so the section boundary was
never detected — everything from the previous header onward (in one observed case, the entire
Skills section) was silently absorbed into the wrong field instead of the Experience section being
populated. Added `work\s+history` and `employment\s+history` as recognized aliases. This heuristic
splitter remains a stub — other real-world headings (e.g. "Professional Experience", "Career
History") may still go unrecognized; see
`tests/intake_extraction/test_extraction.py::test_work_history_header_is_recognized_as_experience`.

## Manual-review routing on low-confidence must-have fields

**Fixed 2026-07-21:** `IngestionGateway._has_low_confidence_must_have()` only checked the
confidence threshold when a field's status was `VERIFIED`. A field that's `UNVERIFIED` (its
section is missing from the resume entirely, e.g. no "Skills:" heading anywhere) never entered
that branch, so a resume missing a must-have-candidate section was silently treated as fully
processed instead of routed to manual review — the opposite of `design.md` §3.2 ("Fields below the
must-have confidence threshold are marked Unverified and routed to manual review") and FR-3. Fixed
by reusing `ExtractedField.meets_must_have_confidence` (already defined on the model, already
false for `UNVERIFIED`) instead of re-deriving the check by hand in the gateway. Found via
`code-review` skill audit against design.md/FR-3, not via a failing test — no existing test
exercised the "section missing entirely, not just short" combination; see
`tests/intake_extraction/test_gateway.py::test_real_world_functional_resume_pdf_with_no_skills_heading_routes_to_manual_review`,
which previously asserted the buggy pass-through behavior and now asserts the correct routing.

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

## Extracted-text log persistence

**Status:** Stubbed — plain append-only file, path chosen by the caller
**What was built:** `TextExtractionLog` (`intake_extraction/text_extraction_log.py`) — appends
every successfully-extracted submission's raw text (PDF text layer, OCR output, or plain-text
fallback) to one growing `.txt` file, with a header per entry (timestamp, channel, candidate
identifier). Wired into `IngestionGateway` as an optional constructor collaborator
(`text_log: TextExtractionLog | None`); when omitted (the default), nothing is written, so this is
opt-in and every existing test/caller is unaffected.
**What a real implementation must satisfy:** the file contains raw candidate resume text, i.e.
personal data — a real deployment needs the same retention/residency treatment as the audit log
above (see "Audit log persistence"), not an indefinitely-growing plaintext file on a local disk.
**Why this default:** requested specifically as a way to inspect what extraction/OCR actually
produced for a real submission without re-running the pipeline by hand each time; deliberately
kept as a plain file rather than reusing `AuditLog`'s `AuditEvent`, since `AuditEvent` has no
free-text payload field and is meant for decision-relevant events, not raw content dumps.

## What this draft does NOT cover yet

This is a rough first draft of Wave 1 only (Module 1: Intake & Extraction, and the minimum of
Module 7: Governance & Audit needed for Module 1 to log through it). **Not yet built:** manual-
review SLA monitoring/alerting, incident routing, weekly operational review, Talent Pool Store,
Candidate Feedback storage, and Modules 2 through 6 entirely (empty placeholder packages only, per
`md/prompt.md` §5's repository layout). See `md/progress.md` for the authoritative checklist.
