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
**Fixed 2026-07-22:** `candidate_name` was hardcoded to `None` for every local-folder submission --
harmless until `cli.py` (below) needed something human-readable to print per candidate and got a
meaningless UUID (`candidate_id`) instead. A real Email/Teams adapter reads the name from the
message envelope; this stub has no envelope, so it now falls back to the filename (minus
extension) as the closest available identifier.

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
**Fixed 2026-07-22:** `IdentityDedupService.match()` used to return on the *first* existing
candidate that produced any signal at all, in list order. With more than one known candidate, an
unrelated person's coincidentally weak name overlap (checked first, landing in the ambiguous band)
could block a later candidate's confident, exact match from ever being found — a real submission
that should have merged into candidate #2 got wrongly flagged ambiguous because of a weak signal
from candidate #1. Fixed by scanning every existing candidate and preferring any confident
(`MERGED_INTO_EXISTING`) result over an ambiguous one, regardless of which came first; see
`tests/intake_extraction/test_dedup.py::test_a_confident_match_wins_even_when_a_weaker_ambiguous_candidate_comes_first`.

## Audit log persistence

**Status:** Resolved on the lightweight/local side only — the real deployment data store remains
pending human decision (data residency, `md/progress.md` §2a)
**What was built:** two `AuditLog`-protocol implementations now exist: `InMemoryAuditLog`
(`governance_audit/audit_log.py`, events live in a Python list, lost on process exit) and
`SqliteAuditLog` (`governance_audit/sqlite_audit_log.py`, events persist to a local SQLite file —
or `:memory:` for tests — and survive a process restart). Callers pick either by constructor call;
nothing else about the protocol changes.
**What a real implementation must satisfy:** durable, append-only storage, retained independently
of application data per SOP 4.3's layered retention (identifiable data erasable; pseudonymized
decision logs retained separately for their own period), on whatever cloud data store `design.md`
§10.1 eventually settles on.
**Why this default:** `SqliteAuditLog` needs no vendor account, network call, or region decision —
it's a temporary bridge so the audit trail survives a restart *now*, not a stand-in for the real
durable/region-aware store design.md §4.2 describes. `InMemoryAuditLog` remains available where
even a local file isn't wanted (e.g. fully ephemeral unit tests).
**Fixed 2026-07-21:** `_row_to_event()` originally re-parsed the stored timestamp with
`datetime.fromisoformat(...).astimezone(UTC)`. `isoformat()`/`fromisoformat()` alone is already a
lossless round trip for both naive and timezone-aware datetimes; the extra `.astimezone(UTC)` call
reinterpreted a *naive* datetime using the local system's timezone, silently shifting its
wall-clock value rather than just relabeling it (no caller passes a naive datetime today --
`datetime.now(UTC)` is used everywhere -- so this was latent, not yet triggered). Removed the
`.astimezone(UTC)` call; see
`tests/governance_audit/test_sqlite_audit_log.py::test_timestamp_round_trips_without_shifting_a_naive_datetime`.
Also added a missing index on `entity_ref`, the column `events_for()` filters by.

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

## Scoring Engine: must-have vs. weighted criteria are two separate lists

**Status:** Interpretation call — the spec is genuinely ambiguous here
**What was built:** `JRP` (`scoring_engine/models.py`) holds `must_have_criteria` (pure pass/fail
gates — a required skill or a minimum-years floor) and `weighted_criteria` (one entry per scored
dimension: Mandatory Skills / Experience Tenure / Educational Level / Project Relevance, each with
a weight, a matching curve, and the requirement value that curve measures against) as two
independent lists, not one list where any of the four named dimensions can itself be tagged
must-have.
**Why this reading:** FR-6's weight table gives "Mandatory Skills" a normal percentage weight
(40% under the General template), which only makes sense if that whole dimension is expected to
be *scored*, not gated. Module-2 doc §4's own guidance ("trainable skills should not be must-have")
also reads more naturally as being about specific requirements (a license, a language, a minimum
tenure) than about gating an entire weighted dimension wholesale. GLOSSARY.md's "a JRP criterion is
either must-have or weighted" is compatible with either reading; this draft picked the one that
keeps FR-6's weight table meaningful. If the intended reading is "any of the four dimensions can be
marked must-have instead of weighted," `WeightedCriterion` and `MustHaveCriterion` would need to
merge into one type with a `must_have: bool` flag — a resettable decision, not a one-way door.
**What a real implementation must satisfy:** FR-7 (must-have vs. weighted tagging), module-2 doc §4
("no score is computed" for a JRP that gates a candidate out).

## Scoring Engine: `CandidateProfile` vs. Module 1's `ExtractedResume`

**Status:** Resolved on the heuristic side — the Module 1 -> Module 2 adapter is built, using the
same kind of regex heuristics as Module 1's own extraction, not a real parsing/NLP engine
**What was built:** `ScoringEngine.score()` (`scoring_engine/engine.py`) takes a `CandidateProfile`
— typed, already-resolved fields (`skills: tuple[str, ...]`, `years_of_experience: float`,
`education_level: EducationLevel`, `project_count: int`) — rather than Module 1's `ExtractedResume`
directly. `scoring_engine/profile_adapter.py`'s `build_candidate_profile()` now maps one to the
other: `years_of_experience` from the largest explicit "N years" mention (not just the first, so
"8 years total, including 3 years as lead" credits 8, not 3), falling back to the *sum* of each year
range's own length (not the overall min-to-max span, which would wrongly count a career-break gap
between two ranges as experience) if no such phrase is found; `education_level` from a fixed
keyword table (PhD/doctorate -> DOCTORATE, master/MSc/MBA -> MASTER, bachelor/BSc/BBA/BS/BA ->
BACHELOR, "associate's degree" -> ASSOCIATE, "high school"/"secondary school" -> HIGH_SCHOOL,
checked highest-degree-first so a resume listing several degrees credits the highest); `skills` and
`project_count` pass through Module 1's lists directly. Missing/`UNVERIFIED` fields degrade to
`0.0`/`EducationLevel.NONE`/`()`, never an exception.
**What a real implementation must satisfy:** the same mapping, backed by real parsing/NLP instead
of regex heuristics, once Module 1's own extraction (see "Structured extraction" above) is upgraded
past its own regex-heuristic stage — this adapter's accuracy is capped by whatever Module 1
actually extracts, not just its own heuristics.
**Why this default:** reuses the extraction module's own "heuristic stub, honestly scoped and
documented" pattern rather than inventing a different convention for the boundary between the two
modules. Known gaps, left deliberately unhandled: word-form numbers ("five years" won't match, only
"5 years"); open-ended ranges ("2019-Present"); overlapping ranges double-count their overlap (the
sum-of-lengths fix targets the more common non-overlapping-gap case, not this rarer one); bare "MS"/
"MA" are deliberately excluded from the keyword table despite "MSc"/"MBA" being included, because an
unqualified 2-letter/-abbreviation match risks colliding with the "Ms." honorific and similar
false positives that "MSc" doesn't; anything else not covered by the keyword table (e.g. a diploma
name that doesn't contain "bachelor"/"BSc"/etc.) resolves to `EducationLevel.NONE`, crediting
nothing rather than guessing. `tests/integration/test_intake_to_scoring_pipeline.py` proves a real
resume can flow from `IngestionGateway.run_once()` through this adapter into `ScoringEngine.score()`
end to end, not just via hand-built `CandidateProfile` fixtures.

## Scoring Engine: Educational Level ratio is an ordinal comparison

**Status:** Interpretation call
**What was built:** `EducationLevel` (`scoring_engine/models.py`) is an ordinal `IntEnum`
(NONE < HIGH_SCHOOL < ASSOCIATE < BACHELOR < MASTER < DOCTORATE). `_ratio_for()`
(`scoring_engine/engine.py`) computes the Educational Level dimension's raw ratio as
`candidate_level / required_level` (e.g. BACHELOR/MASTER = 0.75), then feeds that ratio through the
JRP's configured curve exactly like the other three dimensions.
**Why this reading:** GLOSSARY.md's three matching-curve examples are all framed around a natural
numeric requirement ("5 years of experience"); it says nothing about how a degree-level requirement
should turn into a ratio. Treating the ordinal rank as a numerator/denominator pair reuses the same
curve math as every other dimension rather than inventing a fifth, degree-specific rule, and
produces sensible results (a Bachelor's candidate against a Master's requirement scores 75% before
the curve, not 0% or 100%). This is a judgement call, not a spec requirement — a different, equally
defensible reading (e.g. "meets or doesn't meet" as a step function regardless of the JRP's curve
setting) is possible.
**What a real implementation must satisfy:** FR-8 (curve configurable per dimension) — satisfied
either way; this note exists so the choice is visible rather than an implicit accident.

## Scoring Engine: skill ontology (FR-27)

**Status:** Stubbed — Module 4 owns the real ontology (design.md §3.6)
**What was built:** `SkillOntology` protocol (`scoring_engine/skill_ontology.py`) plus two
placeholder implementations: `IdentitySkillOntology` (exact match only, the `ScoringEngine`
default) and `SynonymMapSkillOntology` (an explicit synonym-group list, e.g. `[("led a team", "team
leadership")]`).
**What a real implementation must satisfy:** Module 4's maintained ontology/synonym table (FR-27),
consumed read-only by the Scoring Engine, never the other way around (design.md §3.6).
**Why this default:** lets `ScoringEngine` be built and tested against a real interface now without
waiting on Module 4; swapping in Module 4's real ontology later is a constructor-argument change,
not a Scoring Engine rewrite.

## Scoring Engine: one-round-one-version enforcement and the NFR-6 rollback hook

**Status:** Flagged rather than stubbed — like malware scanning, these need infrastructure this
draft doesn't have yet, not just Python logic
**What was built:** nothing — `Score` records do carry `scoring_engine_version` (NFR-5), but
nothing yet blocks scoring some candidates in an active hiring round on one engine version and
others on a different one, and nothing monitors live metrics to trigger NFR-6's automatic
rollback to human-assisted mode.
**Why flagged rather than stubbed:** both need a concept this codebase doesn't have yet (a
hiring-round/Application entity to enforce "one version" against, a live metrics feed to watch for
NFR-6) — not meaningfully fakeable as pure scoring logic. Left as an explicit gap for the next
build pass.

## A command-line bridge, not Module 5's real JRP-config UI/dashboard

**Status:** Temporary -- Module 5 (Presentation Layer, design.md §3.8) owns the real JRP
configuration UI and candidate dashboard, and hasn't been started
**What was built:** `scoring_engine/jrp_config.py` (`load_jrp_from_yaml()`/`parse_jrp_config()`)
reads a JRP from a human-editable YAML file instead of requiring hand-written Python
`JRP`/`WeightedCriterion`/`MustHaveCriterion` objects -- weights may be omitted per criterion to
fall back to the selected `weight_template`'s preset. `cli.py` (registered as the
`hr-digital-employee` console script, see `pyproject.toml`) wires the whole pipeline together:
point it at a folder of resumes and a JRP YAML file, and it runs intake -> extraction -> the
profile adapter -> scoring for every resume and prints a ranked report, with a `--audit-db` flag to
persist the run's audit trail to a `SqliteAuditLog` file.
**What a real implementation must satisfy:** design.md §3.8 -- a proper web dashboard (pipeline
overview, filtering, candidate drill-down, comparison tables) and a JRP configuration UI, with the
explicit HR Pass/Reject action (FR-14) that this CLI does not and should not implement (a
command-line tool has no business being the place a candidate's status changes).
**Why this default:** makes the two already-built modules usable by *someone* right now -- editing
a YAML file and running one command -- without prematurely deciding the frontend framework
question design.md §10.4 leaves open, and without building a backend API server (none exists in
this codebase yet) just to serve a UI that isn't designed yet either.

## What this draft does NOT cover yet

This is a rough first draft of Wave 1 (Module 1: Intake & Extraction, the minimum of Module 7:
Governance & Audit needed for Module 1 to log through it) plus a draft of Module 2: Scoring Engine
(must-have gating, weighted/curve-adjusted dimension scoring, tier classification, JRP versioning +
audit logging — all deterministic, no LLM/agent input anywhere in the module, per FR-9), plus a
YAML-config JRP loader and a command-line bridge (`hr-digital-employee`) tying the two modules
together end to end. **Not yet built:** manual-review SLA monitoring/alerting, incident routing,
weekly operational review, Talent Pool Store, Candidate Feedback storage, one-round-one-version
enforcement, the NFR-6 rollback hook, any real web UI/dashboard/API server (Module 5), and Modules
3, 4, and 6 entirely (empty placeholder packages only, per `md/prompt.md` §5's repository layout).
See `md/progress.md` for the authoritative checklist.
