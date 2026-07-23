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

## A Streamlit form for editing a JRP, not module-5 doc §7's "JRP configuration UI" item

**Status:** Temporary convenience layer on top of the YAML bridge above -- still not Module 5
**What was built:** `jrp_editor/` -- `config_builder.py` builds/reads the same dict shape
`jrp_config.py` parses (Streamlit-free, independently unit-tested), and `app.py` is a one-page
Streamlit form over it: HR fills in weights/must-haves/curves through number inputs, selectboxes,
and a dynamic table instead of hand-editing YAML, sees a live weight-sum indicator and the
Educational-Level-weight guideline warning, and gets the same `JRPConfigError` validation the CLI
enforces before a "Save YAML" button is enabled. `launcher.py` registers the
`hr-digital-employee-jrp-editor` console script so running it doesn't require knowing `streamlit
run <path>` or the app's file location. Streamlit itself is an optional dependency (`pip install
".[ui]"` / `uv sync --extra ui`) -- `pyproject.toml`'s `streamlit` mypy override
(`ignore_missing_imports` + `follow_imports = "skip"`) keeps `mypy src` passing whether or not it's
installed, since only `app.py`/`launcher.py` import it.
**What a real implementation must satisfy:** module-5 doc §7's actual "JRP configuration UI" item
means this embedded in the real dashboard, behind auth, with a change history and no separate
process to launch -- this form has none of that, same caveat as the CLI bridge above.
**Why this default:** a local one-page form is a large convenience jump over hand-written YAML for
close to no build cost, and doesn't require deciding design.md §10.4's frontend framework question
or building a backend API server to get there -- it's the same "usable by *someone* right now"
tradeoff as the CLI bridge, one layer higher.
**A dependency-environment note, not a design decision:** installing the `ui` extra pulls in
`streamlit -> pandas -> numpy`, and numpy's bundled stub uses PEP 695 `type` statement syntax that
mypy only parses at `python_version >= 3.12` -- with the project's prior `python_version = "3.11"`,
`mypy src` failed with a syntax error inside `numpy/__init__.pyi` itself whenever both `dev` and
`ui` extras were installed together (PIL.ImageCms, a pre-existing dependency, imports numpy under
`TYPE_CHECKING`, and per-module `follow_imports = "skip"` overrides aimed at `numpy`/`PIL.ImageCms`
did not suppress it in this mypy version). Fixed by bumping `[tool.mypy] python_version` to `3.12`
-- this only loosens which stub syntax mypy's parser accepts; it does not change `requires-python`
(still `>=3.11`) and this project writes no 3.12-only syntax of its own.

## AI-Assisted Content Generation: the second LLM provider

**Status:** Stubbed — pending human decision (design.md §10.2, `md/progress.md` §2a)
**What was built:** `LLMProvider` protocol (`ai_content/llm_provider.py`) with one method,
`generate_summary_sentences()`. `TemplateLLMProvider` implements it deterministically and
offline: each non-empty source passage becomes one factual sentence built directly from its own
text, so every sentence is anchorable by construction (no hallucination risk from the stub itself).
**What a real implementation must satisfy:** same protocol, backed by a real single-shot LLM API
call (Claude, OpenAI, Azure OpenAI, or other — not yet chosen); its output still passes through
`anchoring.py`'s verification before reaching a `CandidateSummary`, exactly like the stub's does.
**Why this default:** lets every other piece of Module 3 (anchoring/drop-unanchored logic, question
generation, red-flag detection, version stamping, the hallucination-audit hook) be built and tested
now without an API key, network call, or vendor commitment.

## AI-Assisted Content Generation: sentence-anchoring threshold

**Status:** Judgement call, not a spec number -- **plus a confirmed, demonstrated gap, flagged
rather than patched (2026-07-22 security review)**
**What was built:** `anchoring.py`'s `MIN_PASSAGE_COVERAGE = 0.5` -- a sentence is anchored to a
source passage if at least half of that passage's significant (non-stopword, length >= 3) words
appear in the sentence. Deliberately checks *passage-into-sentence* coverage, not the reverse, so a
sentence's own framing/connector words (which a real, paraphrasing LLM would add more of than this
codebase's verbatim-leaning template) don't dilute the match.
**What a real implementation must satisfy:** FR-10's "every sentence carries a source-passage
anchor; unanchored sentences are dropped" -- the exact coverage threshold isn't specified by the
SOP and may need tuning once a real (paraphrasing) LLM is in the loop.
**Why this default:** 0.5 is generous enough that the template stub's own boilerplate wording
never causes a false negative (see `tests/ai_content/test_summary_generator.py`), while still
catching a sentence introducing content absent from every passage (T3.2).
**Confirmed gap:** because coverage is checked in only one direction, a sentence containing 100% of
a passage's words *plus an arbitrary amount of additional, unrelated content* is still scored as
fully anchored -- the additional content is never checked against anything. Verified directly:
```
passages = (SourcePassage(field_name="skills", text="Python, SQL"),)
sentence = ("The candidate is a Python SQL expert who was convicted of embezzling money from a "
            "previous employer and has 25 years managing nuclear reactors.")
anchor_for(sentence, passages)  # -> "skills" (fully anchored, NOT dropped)
```
**Why this isn't patched with a reverse-direction/bidirectional threshold:** it looks like an easy
fix (also require some fraction of the *sentence's* tokens to come from the passage), but measured
against real phrasing this doesn't actually separate the fabrication from legitimate content. A
reasonable, non-hallucinated LLM paraphrase of the same "Python, SQL" passage --
*"The candidate demonstrates strong proficiency in Python and SQL, reflecting solid technical
skills applicable to backend development roles"* -- has a sentence-token coverage ratio of **0.14**.
The fabricated example above measures **0.125** -- nearly indistinguishable from the legitimate
sentence by this metric. A threshold loose enough to admit normal paraphrasing barely blocks the
attack; a threshold tight enough to reliably block it would also reject legitimate LLM output,
defeating the summary feature entirely. Word-overlap counting cannot tell "descriptive filler" and
"fabricated fact" apart -- both are just "words absent from the passage." A real fix needs semantic
verification (e.g. an NLI/entailment check, or a second LLM call asking "is this sentence entailed
by this passage") that this stub does not implement, the same category of gap as malware scanning
or the retention scheduler elsewhere in this file: a real-infrastructure problem, not a tunable
constant. **Currently low live-impact** only because `TemplateLLMProvider` (the only wired-in
provider) never fabricates content in the first place -- this is exactly the check a real LLM
provider would need to lean on once one is plugged in (`llm_provider.py`'s vendor choice is still
open), and today it would not catch the failure mode above.

## AI-Assisted Content Generation: hallucination-rate suspension threshold

**Status:** Flagged rather than stubbed — this is a real-world decision, not a code gap
**What was built:** `hallucination_audit.is_suspension_triggered(hallucination_rate, threshold)`
-- the *mechanism* is real and tested, but it takes `threshold` as a required argument with no
default.
**Why flagged rather than stubbed:** module-3 doc §6 says the SOP references "the agreed
threshold" without ever giving a number. Every other default in this codebase (tier thresholds,
Educational Level weight guidance, buffered-curve constants) ships because the SOP or GLOSSARY
gives a concrete figure to ship; this one doesn't, so inventing one here would be presenting a
guess as policy. `HallucinationAuditLog.sample()` (the actual monthly-audit query/export hook
module-3 doc §4 asks this module to support) is fully built and usable today regardless.

## AI-Assisted Content Generation: only the summary goes through `LLMProvider`

**Status:** Interpretation call, now documented (found during self-review, wasn't written down
the first time)
**What was built:** `SummaryGenerationService` is the only piece of Module 3 that calls
`LLMProvider.generate_summary_sentences()`. `interview_questions.py` and `red_flags.py` are pure,
deterministic Python (score-breakdown targeting; regex-based date/keyword heuristics) — neither
imports `llm_provider` at all, and neither has a `model_version`/`prompt_version` field, unlike
`CandidateSummary`.
**Why this reading:** design.md §3.5 describes all three outputs (summary, questions, red flags)
as coming from "a standard LLM API call," which read literally would put all three behind
`LLMProvider`. This draft narrowed that: FR-10's anchoring requirement exists specifically because
free-text summary generation is genuinely hallucination-prone, but "which score dimensions are
strong/weak" and "are there overlapping employment dates" are already fully answered by Module 2's
structured `Score.breakdown` and Module 1's structured text — asking an LLM to *re-derive* that
from scratch would be strictly less reliable and less auditable than reading the structured data
directly, and neither FR-12 nor module-3 doc §4 requires anchoring for questions/flags the way
FR-10 does for the summary. A real implementation could still route questions/flags through an
LLM for more natural phrasing; this draft prioritized determinism where determinism was available.
**What a real implementation must satisfy:** FR-12 (interview questions, red-flag hints) — both are
functionally satisfied by the deterministic approach; a future revision replacing them with LLM
calls would need to add the same anchoring discipline FR-10 already requires of the summary.

## AI-Assisted Content Generation / Scoring Engine: a duplicated year-range regex

**Status:** Accepted duplication, now documented (found during self-review)
**What was built:** `ai_content/red_flags.py` and `scoring_engine/profile_adapter.py` each define
their own, byte-for-byte identical `_YEAR_RANGE_PATTERN = re.compile(r"\b((?:19|20)\d{2})\s*-\s*
(?:19|20)\d{2})\b")` rather than sharing one implementation.
**Why this default:** matches the same reasoning as `SkillOntologyRepository`'s zero-import design
(see below) — `ai_content` and `scoring_engine` are meant to stay decoupled per FR-9's separation
principle, and this project's modules are each intentionally self-contained (Module 1 and Module 2
don't share a text-parsing utility module either). The regex is small enough that duplicating it
costs less than introducing a shared-utility module both packages would depend on. If a third
module needs the same pattern, that's the point to extract it — to a shared, dependency-free
location neither `ai_content` nor `scoring_engine` needs the other to reach.

## Fairness & Compliance: statistical significance test

**Status:** Resolved — one of module-4 doc §4's two acceptable options was picked
**What was built:** `adverse_impact.standardized_difference_test()` -- a two-proportion z-test
(`SIGNIFICANCE_Z_CRITICAL = 1.96`, the standard two-tailed p<0.05 critical value).
**Why this choice over chi-square:** module-4 doc §4 accepts either "chi-square or standardized
difference." A z-test needs only `math.sqrt`; computing an exact chi-square p-value would need
scipy's inverse CDF (or a hand-rolled approximation) just to avoid a new dependency for a stub-era
fairness check. The z-test is mathematically equivalent to a chi-square test for a 2x2 table at
1 degree of freedom, so nothing is lost in rigor for the two-group case this module currently
handles.

## Fairness & Compliance: `SkillOntologyRepository` has zero import dependency on `scoring_engine`

**Status:** A deliberate design choice, not a spec mandate
**What was built:** `SkillOntologyRepository.resolves_same_skill(a, b)` (`fairness_compliance/
skill_ontology_store.py`) has the exact method signature `scoring_engine.skill_ontology
.SkillOntology` (a `Protocol`) requires. Because Python `Protocol`s are structural, a
`SkillOntologyRepository` instance can be passed directly as `ScoringEngine`'s `skill_ontology`
constructor argument with **no import of `scoring_engine` anywhere in `fairness_compliance`** --
see `tests/fairness_compliance/test_skill_ontology_store.py`'s
`test_t4_13_repository_satisfies_the_scoring_engines_skill_ontology_protocol_structurally`.
**Why this default:** module-4 doc §4 says Module 4 "owns updates to the ontology; Module 2 never
writes to it" -- describing a one-way *data* flow (Module 4 produces, Module 2 consumes). Making
that a one-way *import* dependency too (rather than fairness_compliance importing scoring_engine
just to wrap its stub ontology classes) keeps the two modules as loosely coupled as design.md's
architecture calls for, and mirrors the one-directional invariant already enforced between
`ai_content` and `scoring_engine` (`tests/test_architectural_invariants.py`). This is a nice-to-have
this draft chose to build, not something md/prompt.md's non-negotiable constraints require.

## Fairness & Compliance: jurisdiction detection vs. the strictest-default rule

**Status:** Split — the default rule is real logic; detection itself is flagged, not stubbed
**What was built:** `jurisdiction.resolve_jurisdiction()` implements module-4 doc §4's
"default to strictest framework when jurisdiction is undetermined" rule in full (defaults to
`Jurisdiction.EU_GDPR`). Actually *determining* a candidate's jurisdiction (from a declared
address, IP geolocation, etc.) is not built.
**Why flagged rather than stubbed:** jurisdiction detection needs real candidate-location data this
codebase has no source for yet -- same category of gap as Module 1's malware scanning (needs real
infrastructure/data, not fakeable as pure logic). The judgement call worth flagging on its own:
ranking GDPR as "strictest" among PDPO/GDPR/PIPL is this draft's interpretation (GDPR Article 22's
automated-decision rights are the most restrictive of the three baselines this system cites), not
a ranking the SOP states explicitly.

## Fairness & Compliance: access/correction request handling is a workflow skeleton

**Status:** Stubbed — the request lifecycle is real; fulfillment against real candidate data is not
**What was built:** `AccessRequestService` (`fairness_compliance/access_requests.py`) tracks a
request through `received -> in_progress -> fulfilled`, audit-logging every transition (FR-26).
**What a real implementation must satisfy:** actually locating and returning/correcting a
candidate's held data -- which needs a real candidate-data store this codebase doesn't have yet
(Module 1's `IdentityDedupService` holds only enough fields to dedupe, not a full PII record).
**Why this default:** the request-tracking workflow (states, audit trail, who-requested-what) is
real, testable process logic independent of which data store eventually backs it -- building that
now doesn't need to wait on a storage decision.

## Fairness & Compliance: retention scheduler and quarterly re-test scheduler

**Status:** Flagged rather than stubbed — like malware scanning and the Scoring Engine's rollback
hook, these need a real recurring-job scheduler, not just Python logic
**What was built:** the pure eligibility checks (`retention.is_eligible_for_routine_deletion()`,
`is_eligible_for_withdrawal_deletion()`) are real and tested. Nothing calls them on a recurring
schedule, and nothing automatically re-triggers a four-fifths test on a quarterly cadence or on a
JRP weight/must-have change (FR-20's "not only on a fixed calendar schedule" trigger).
**Why flagged rather than stubbed:** module-4 doc §5 says this "coordinates with Module 7," which
doesn't have a scheduler either yet -- there's no live infrastructure in this codebase for either
module to hook a recurring job into. `_DAYS_PER_MONTH = 30` in `retention.py` is also a documented
approximation (calendar-month arithmetic without a dependency like `dateutil`), not exact.

## A stale docstring caught while building Module 3

**Fixed 2026-07-22:** `ai_content/__init__.py` originally said "Must never import from
scoring_engine," citing md/prompt.md §2 invariant 1. Invariant 1 is actually one-directional —
`scoring_engine` must never import `ai_content`, and `ai_content` must never *construct* a `Score`
— reading an existing `Score` for interview-question targeting is expected and required by
module-3 doc's own Dependencies section. Corrected the docstring to state the real (one-way)
constraint and pointed it at `tests/test_architectural_invariants.py`, which enforces it.

## Security review (2026-07-22): two real vulnerabilities found and fixed

**1. The JRP editor's Streamlit server bound every network interface by default, unauthenticated.**
`streamlit run` with no `--server.address` binds all interfaces, not just localhost -- confirmed
directly: its own startup banner printed a LAN "Network URL" and a public "External URL" alongside
the local one. `jrp_editor/app.py`'s "Load"/"Save YAML" fields take an arbitrary filesystem path
with no login in front of them, so the default would have let anyone who could reach the port (LAN,
or the internet if it's forwarded) read or write any file the process can access, with no
authentication at all -- effectively a remote arbitrary file read/write primitive bolted onto a
form meant for one HR user on one machine. **Fixed:** `launcher.py` now passes `--server.address
127.0.0.1` explicitly; re-ran the same startup check afterward and only the loopback URL is printed.
**Residual risk:** this only prevents *accidental* exposure from the default. If this tool is ever
meant to be reachable by more than one trusted local user, it needs real authentication and path
confinement (e.g. restricting Load/Save to a configured directory) added first -- neither exists
today.

**2. A resume submitted as an oversized image crashed the entire intake batch, unhandled.**
`ocr.py`'s `extract_text()` only caught `UnidentifiedImageError` around `Image.open()`. A crafted
image whose header declares far more pixels than its actual data backs up (reproduced with a PNG
declaring 60000x60000 dimensions but one truncated scanline of real data) makes Pillow raise
`DecompressionBombError` instead, which propagated uncaught through `pdf_text.py` and
`gateway.py`'s `run_once()` (no per-submission try/except exists there) and crashed the whole
ingestion run -- not just that one candidate's processing. Resume input is already treated as
adversarial elsewhere in this module (`injection_screening.py`'s hidden-text/instruction-pattern
defenses); this was the same threat model with an image-based angle left uncovered. **Fixed:**
`extract_text()` now also catches `Image.DecompressionBombError` and routes it through the same
"unparseable, route to manual review" path every other malformed file already takes -- no new
behavior, just closing a gap in existing handling. Regression test:
`tests/intake_extraction/test_ocr.py::test_decompression_bomb_image_is_unparseable_not_a_crash`
(a fixture builds the oversized-header PNG directly via raw chunk bytes, since actually rendering a
60000x60000 image with Pillow to test this would itself exhaust memory).

## Security + logic review, round 2 (2026-07-22): seven more real bugs found and fixed

Three parallel reviews (intake/CLI/JRP-editor, scoring engine, AI-content/fairness) each verified
their findings by actually running the real code before reporting them. All seven below were
independently reproduced again here before fixing. One additional finding (anchoring.py's
one-directional coverage check) is written up separately above, since it's a demonstrated gap that
is deliberately *not* code-patched -- see that entry for why.

**1. (High) One bad submission could crash the entire intake batch, silently dropping everything
queued after it.** `IngestionGateway.run_once()`/`_process_submission` (`gateway.py`) had no
exception boundary beyond the specific cases it already checks for (unparseable, injection, low
confidence, ambiguous identity) -- anything else escaping, e.g. a corrupted PDF making pypdf raise
something other than `PyPdfError`, propagated out of `run_once()` uncaught. **Fixed:** added a
`QueueReason.PROCESSING_ERROR` and wrapped the per-submission call in `run_once()` in a
`try/except Exception`, routing anything unexpected to manual review the same way every known
failure mode already is, instead of aborting the batch. Regression tests in
`tests/intake_extraction/test_gateway.py` cover both the crash-prevention itself and that the rest
of the batch still processes after one bad submission.

**2. (High) Resume files with an uppercase/mixed-case extension were silently never picked up at
all.** `channel_adapters.py`'s `LocalFolderChannelAdapter` matched files via `Path.glob("*.pdf")`-
style patterns, whose case sensitivity follows the OS (case-insensitive on Windows, case-sensitive
on the Linux this would actually deploy to) -- a real-world `Resume.PDF` or scanner output like
`SCAN0001.PDF` would never be read, queued to manual review, or logged anywhere on a case-sensitive
filesystem: a silent, un-audited candidate loss, worse than routing to manual review because there's
no trace it happened. **Fixed:** match via `Path.suffix.lower()` against a fixed extension set
instead of OS-dependent glob patterns.

**3. (Medium) A TOCTOU race between listing a folder and reading each file could crash the whole
fetch.** Same file, between building the list of new paths and reading each one's bytes -- a file
deleted/moved in that window (a concurrent cleanup job, a flaky network share) raised an uncaught
`FileNotFoundError`, losing every other file in that fetch too, not just the one that vanished.
**Fixed:** `read_bytes()` per file is now wrapped in `try/except OSError`, skipping just that file.

**4. (High) A malformed `minimum_years` in a JRP YAML parsed successfully and only crashed later,
mid-scoring.** `MustHaveCriterion.__post_init__` (`models.py`) checked only that
`minimum_years is not None`, never that it was numeric -- `minimum_years: five` passed
`load_jrp_from_yaml` with no error, then crashed every subsequent `engine.score()` call with
`TypeError: '>=' not supported between instances of 'int' and 'str'`. **Fixed:** now validates
`minimum_years` is a non-bool `int`/`float` and non-negative, raising the documented
`JRPConfigError` at load time instead of crashing later in the scoring hot path.

**5. (High) A malformed `tier_thresholds` in a JRP YAML raised an uncaught `AttributeError` instead
of a clean `JRPConfigError`.** `_parse_tier_thresholds` (`jrp_config.py`) called `.get(...)`
assuming its argument was always a mapping -- a YAML list there (`tier_thresholds: [1, 2, 3]`)
broke that assumption. **Fixed:** validates the value is a mapping first, raising `JRPConfigError`.

**6. (Medium-High) A scalar `required_skills` in a JRP YAML silently produced wrong, single-letter
"skills" with no error at all.** `_parse_weighted_criterion` (`jrp_config.py`) called
`tuple(required_skills)` on whatever was there -- if HR wrote `required_skills: Python` (forgetting
the `[...]`), Python's `tuple()` iterates the string's characters, silently becoming
`('P', 'y', 't', 'h', 'o', 'n')`. Verified this tanks the `mandatory_skills` dimension (a candidate
who should score 100 scored 60) with no diagnostic anywhere. **Fixed:** now validates
`required_skills` is a list/tuple when present, raising `JRPConfigError` instead.

**7. (Medium) Overlapping/concurrent job date ranges were double-counted or misread as a gap.**
Both `profile_adapter.py`'s `years_of_experience` fallback (summing each `YYYY-YYYY` range's own
length) and `red_flags.py`'s `_detect_employment_gap` (checking adjacent ranges after sorting) only
looked at raw, unmerged ranges. A candidate with a continuous 2015-2020 role plus two shorter
concurrent engagements inside it got `8.0` years credited instead of the correct `5.0`
(profile_adapter), and a spurious "gap between 2017 and 2018" flag despite being continuously
employed the whole time (red_flags) -- verified both independently. A separate, related bug in the
same code: neither file validated a parsed range's `start <= end`, so a single typo'd/reversed date
(`"2020-2015"`, plausible from OCR or a typing slip) could be sorted ahead of a later correct range
and fabricate a multi-year gap around it. **Fixed:** both files now filter out `end < start` ranges
before use, and both now merge overlapping ranges (a small interval-merge helper, duplicated in each
file rather than shared -- see the existing "duplicated year-range regex" entry above for why these
two modules stay decoupled from each other) before summing/scanning for gaps.

## Security + logic review, round 3 (2026-07-22): thirteen more real bugs found and fixed

Four parallel reviews (dedup/extraction/review-queue, scoring-engine internals, ai_content/
fairness_compliance internals, jrp_editor+cli+governance_audit), every finding verified by
actually running the real code (including the JRP editor's Streamlit UI, via `AppTest`) before
fixing.

**Identity/data-integrity (`intake_extraction/dedup.py`):** an *exact* full-name match with no
corroborating email/phone used to auto-merge outright -- two different real candidates sharing one
common name (e.g. two "John Smith"s) were silently merged into one profile, with no human ever
seeing it, directly contradicting the module's own "never auto-merge on an uncertain match"
principle. Worth noting: `LocalFolderChannelAdapter` never populates email/phone at all today, so
every real match in the current pipeline was already name-only. **Fixed:** a name match, however
exact, is now always `AMBIGUOUS`, never `MERGED_INTO_EXISTING` -- only email/phone can drive an
automatic merge. Separately, email/phone comparison was exact-string (case-sensitive, no
formatting normalization) -- `Elizabeth.Windsor@Example.com` vs `elizabeth.windsor@example.com`, or
`+1 (555) 123-4567` vs `15551234567`, silently created two profiles for one real person. **Fixed:**
both are now normalized before comparison (email case-folded; phone reduced to digits only).

**Resume-parsing correctness (`intake_extraction/extraction.py`):** a section header word
appearing as the last word of an ordinary prose line with no trailing punctuation (e.g. a summary
line ending "...continuous learning and education") satisfied `keyword + optional colon + newline`
just as validly as a real standalone header, silently absorbing the real section that followed into
the wrong field. **Fixed:** headers are now anchored to the start of a line, with a bounded
two-word prefix allowance so real subheading-style lines (e.g. "Adult Care Experience", already
relied on by this module's own real-world-template tests) still work.

**Injection screening (`intake_extraction/injection_screening.py`):** the hidden-white-text
pattern had no distance bound -- *any* two white-color CSS mentions anywhere in a whole document
(not just a genuinely hidden span) bridged everything between them and got stripped, destroying
real, unrelated resume content that was never actually hidden. **Fixed:** bounded the match to a
realistic hidden-payload length (300 characters) rather than the whole document.

**Text-log integrity (`intake_extraction/text_extraction_log.py`):** candidate-supplied text was
written verbatim, unescaped, using a fixed/guessable delimiter -- a resume embedding that exact
separator sequence could forge what looks like a second, convincing log entry attributed to a fake
candidate/date. **Fixed:** every line of the untrusted text is now indented, so a forged header
can't start at column 0 the way a real one does. (This is the human-review text log, not the
compliance-relied-upon `governance_audit` trail -- see the existing entry on this file.)

**Scoring determinism (`scoring_engine/models.py`, `skill_ontology.py`):** `nan < 0` is `False`, so
a NaN `years_of_experience` passed `CandidateProfile`'s validation and silently poisoned the whole
downstream score (`total_score=nan`) with no exception anywhere -- a direct violation of FR-9's
determinism guarantee. **Fixed:** explicit `math.isnan()` check. Separately, `IdentitySkillOntology`
(the production default until Module 4 ships) claimed whitespace-insensitivity but only
`.strip()`ped the ends, not internal runs -- "Team  Leadership" (doubled internal space) wrongly
failed to match "Team Leadership", a plausible false-negative must-have rejection against real,
irregularly-spaced OCR/PDF-extracted text. `SynonymMapSkillOntology` had the same internal-
whitespace gap, plus a silent-overwrite bug: a later synonym group sharing a term with an earlier
one silently broke the earlier group's synonymy with no error. **Fixed:** normalization now
collapses internal whitespace too, and an overlapping group now raises instead of silently
corrupting the earlier mapping.

**JRP storage (`scoring_engine/jrp_repository.py`):** `save()` had no version-monotonicity check --
accidentally saving an older/duplicate version silently overwrote a newer one, with only a forensic
(not preventive) audit trail; any candidate scored afterward was silently scored against stale
criteria. Separately, `save()` wrote to the store *before* audit-logging, so a failure recording the
audit event still left the new JRP live with no corresponding audit entry -- undermining "every JRP
change is audit-logged." **Fixed:** version must now strictly increase (else `ValueError`), and the
audit log is written before the store, so a failure leaves nothing changed.

**Fairness ontology (`fairness_compliance/skill_ontology_store.py`):** the same silent-overwrite gap
as `SynonymMapSkillOntology` above -- a routine ontology edit could silently make a JD requiring
"C#" stop matching a candidate who listed "CSharp", with zero visibility into why. Same fix
(overlap raises instead of silently corrupting).

**Interview questions (`ai_content/interview_questions.py`):** when every dimension already
cleared the same threshold (e.g. every dimension a strength), the strongest/weakest fallback could
still pick a dimension that already got the *opposite*-angle question, producing a self-
contradictory pair ("you scored strongly on X" and "your profile shows a gap in X" about the same
X). **Fixed:** the fallback is now skipped (not forced) when there's genuinely nothing left in the
opposite direction to probe.

**CLI error handling (`cli.py`):** an `--audit-db` path that exists but isn't a SQLite file, or is a
SQLite file with an incompatible schema, raised an uncaught `sqlite3` exception -- a raw traceback
(the incompatible-schema case surfaced only later, mid-pipeline, since `CREATE TABLE IF NOT EXISTS`
silently no-ops against an existing table). **Fixed:** both are now caught and reported as a clean,
actionable error with a non-zero exit code.

**JRP editor (`jrp_editor/app.py`) -- CRITICAL:** every per-dimension widget (weight/curve/
required-skills/etc.) used a fixed `key=`. Once a keyed Streamlit widget is instantiated, only
`st.session_state[key]` -- never a later `value=` argument on a subsequent rerun -- determines what
it displays (confirmed directly via Streamlit's `AppTest` harness). Loading an existing JRP file, or
switching the weight-template dropdown, updated the plain `weighted_criteria` list and showed a
green "Loaded"/"Weights reset" confirmation -- while every widget kept silently showing the
*previous* JRP's stale values underneath. HR editing what they believed was the loaded JRP was
actually still editing the old one, with a false-positive success message telling them otherwise.
**Fixed:** loading a file or switching templates now writes each row's values directly into the
widgets' own session_state keys before they render, which is what Streamlit's own widget model
requires for this to work; the redundant `value=`/`index=` arguments were removed to match
Streamlit's own recommended pattern (their presence alongside a pre-set session_state key produced
a policy warning). Regression tests use `AppTest` and are skipped (not failed) when the optional
`ui` extra isn't installed.

## Security + logic review, round 4 (2026-07-22): six more real bugs, mostly regressions from
## today's must-have-semantics change

Three parallel reviews (scoring-engine internals, fairness_compliance/ai_content, intake_extraction
+cli+jrp_editor), each specifically briefed to scrutinize today's `engine.py` must-have rewrite for
regressions, every finding reproduced against the real code before fixing.

**Root cause found independently by two reviews:** `Score.failed_must_have_label` (singular
`str | None`) could only ever name the FIRST failing must-have criterion, even when several failed
-- silently hiding the rest from both `cli.py`'s report and `fairness_compliance/
explainability.py`'s candidate-facing explanation (FR-25). This directly undercut today's own
spec-revision goal ("HR sees the whole profile before deciding") with a same-day regression: a
candidate failing 3 must-haves showed only 1. **Fixed:** renamed to `failed_must_have_labels: tuple
[str, ...]` (`scoring_engine/models.py`); `engine.py`'s `score()` now collects every failing
criterion, not just the first (`next(...)` -> a generator collected in full); `explainability.py`
and `cli.py` both render the full set, joined, instead of a single label.

**`cli.py`'s ranked report -- a disqualified candidate could rank #1 as "high_match" with the
must-have failure easy to miss on a skim.** Before today's `engine.py` change, a failed must-have
always forced `total_score=0.0`, so disqualified candidates sorted to the bottom automatically; that
invariant disappeared once the score is always fully computed. A candidate failing one must-have
but excellent on every weighted dimension can legitimately score 100/high_match (this is the
*intended* new behavior per SOP 2.2.2/2.2.4 -- the score must not be suppressed), but the report
gave no visual distinction beyond the existing per-row "FAIL: ..." text in the last column. **Fixed:**
sort order is unchanged (score-only ranking matches "used solely for ranking" in SOP 1.4/FR-13
literally), but a disqualified row's tier now carries a trailing `*` and a footnote explains it when
any row is disqualified -- a deliberately minimal fix, not a ranking-rule change, since the SOP does
not specify must-have-passed-first ordering.

**`scoring_engine/profile_adapter.py:45` crashed the whole candidate (and the whole CLI batch, no
exception boundary around per-candidate scoring in `cli.py`) on an oversized digit run before
"years."** `float(max(int(m) for m in explicit_matches))` -- `int()` parses an arbitrarily long
digit run fine, but the surrounding `float()` conversion raises `OverflowError` on it (garbled OCR,
copy-paste artifact, or adversarial input -- same untrusted-input threat model already defended
elsewhere). **Fixed:** bounded the regex to 1-3 digits (`\d{1,3}`), which both prevents the crash
and stops an absurd figure from ever being treated as literal.

**`ai_content/red_flags.py`'s gap and inconsistency detectors silently dropped every match after
the first.** `_detect_employment_gap`/`_detect_inconsistency` both `return`ed on the first hit inside
their loop; `detect_red_flags` calls each detector exactly once, so a resume with two independent
employment gaps, or two independent overlapping-date pairs, only ever surfaced one -- the second was
never merged into the first's description, just silently gone. **Fixed:** both now collect every
match into a tuple (`_detect_employment_gaps`/`_detect_inconsistencies`), and `detect_red_flags`
extends its flag list from all of them.

**`intake_extraction/dedup.py`'s `_compare()` could still auto-merge two different people, via a
different vector than round 3's name-only fix.** The truthiness guard checked the *raw*
phone/email string was non-empty, then compared *normalized* values for equality -- so two
different people whose raw phone/email are non-empty punctuation-only garbage that both normalize
to `""` (e.g. phone `"--"` vs `"()"` , or email `"   "` vs `"\t"`) collided and merged with no human
review, the same anti-pattern round 3 targeted. **Fixed:** the truthiness check now runs on the
*normalized* value, not the raw one.

**`jrp_editor/app.py`'s must-have criteria table had zero columns on every brand-new JRP.**
`st.data_editor(st.session_state.must_have, ...)` was passed a bare Python list; Streamlit infers a
data_editor's schema from the data it's given, and none of the 5 weight-template presets seed a
must-have row, so the common case (`[]`) produced a table with no `kind`/`label`/`required_skill`/
`minimum_years` columns at all -- confirmed via the widget's serialized Arrow schema through
`AppTest` (`"columns": []`). HR had no way to add a must-have criterion through the form in that
state. **Fixed:** now passes a `pandas.DataFrame(st.session_state.must_have, columns=[...])` with
an explicit column list, so the schema is defined even with zero rows; also updated the section's
caption, which still described the pre-revision "no score at all" gating behavior. Added a `pandas`
mypy override (same `ignore_missing_imports`/`follow_imports=skip` shape as the existing `streamlit`
override) since `app.py` now imports it directly.

261 tests (254 -> 261; seven new regression tests -- one for the multi-failure fix, two each for
the red-flags and dedup fixes, one each for profile_adapter and jrp_editor; the ranking-display fix
is a report-formatting change with no separate assertion beyond the existing `test_cli.py`
coverage); ruff/mypy clean.

## Spec revision (2026-07-22): must-have gating semantics changed in the source SOP

The user supplied an updated source document, `HR_Digital_Employee_Blueprint (2).docx`. Diffing it
against the backup Word keeps of the previous save (`HR_Digital_Employee_Blueprint (2).backup.docx`,
also dated 2026-07-22) showed exactly one substantive change, spanning SOP §2.2.2 and §2.2.4: a
failed must-have criterion used to disqualify the candidate outright with no weighted score
computed; the revision changes this so the weighted score is *always* computed, and a failed
must-have is flagged alongside the result instead of replacing it -- HR sees the full profile before
deciding, and the system never auto-rejects. Everything else in the document is byte-for-byte
identical in content to the version `requirement.md`/`design.md` were originally built from
(confirmed by extracting both `.docx` files' `word/document.xml` and diffing the paragraph text).

**Fixed to match:** `scoring_engine/engine.py`'s `score()` -- removed the early-return path that
short-circuited with `total_score=0.0`, `tier=LOW_MATCH`, `breakdown=()` on the first failed
must-have; must-have evaluation and weighted-dimension scoring now both always run, and
`passed_must_have`/`failed_must_have_label` are set from whichever (if any) must-have criterion
failed, alongside the real score/tier/breakdown. `fairness_compliance/explainability.py`'s
`explain_score()` used to return an empty-breakdown explanation replacing the score entirely on a
must-have failure; it now appends the failure reason to the full score explanation instead, since a
candidate requesting an explanation (FR-25) is entitled to see the complete basis for their result,
not just the reason they were flagged. Updated `requirement.md` FR-7, `design.md` §3.4,
`module-2-scoring-engine.md` §4/§7, and `test.md` T2.3/TE2E.2 to state the new semantics explicitly
(FR-7 previously only said criteria are tagged must-have/weighted, not what happens on failure).
Two tests encoded the old semantics as assertions and were rewritten against hand-verified numbers
rather than loosened: `test_t2_3_...` (`tests/scoring_engine/test_engine.py`) and
`test_explanation_for_a_must_have_failure_...` (`tests/fairness_compliance/test_explainability.py`).
No other production code depended on the old short-circuit behavior (checked via a repo-wide grep
for `passed_must_have`/`failed_must_have_label` usage) -- `cli.py`'s report printer and
`ai_content`'s interview-question/red-flag generation already treated `Score` fields generically and
needed no change.

## Security + logic review, round 5 (2026-07-22): a test-coverage/architectural audit plus six
## more real bugs found and fixed

Three parallel reviews: (1) a test.md coverage-gap and architectural-invariant audit (rather than
another "find bugs in file X" sweep), (2) an end-to-end adversarial walkthrough chaining real
objects across module boundaries with boundary/Unicode/malformed inputs, (3) a fresh deep sweep of
`governance_audit`, `manual_review_queue.py`, `channel_adapters.py`, `ocr.py`/`pdf_text.py`, and
`jrp_editor/config_builder.py` -- files earlier rounds touched only in passing. Every finding
reproduced against real code before fixing.

**Most consequential: `extraction.py`'s section-header regex was English-keyword-only, silently
violating SOP 2.1.1's own explicit consistency guarantee.** Confirmed: an identical candidate
(same skills/years/degree/projects) scored 60.0/Mid Match with plain-English headers but
0.0/Low Match with Chinese headers -- every field went `UNVERIFIED` since "技能"/"工作经验"/
"教育背景" never matched. This isn't a hypothetical edge case -- SOP 2.1.1 explicitly requires
validated accuracy on "mixed Chinese-English text," and this system's own user base is Hong
Kong-based. **Fixed:** each of the four section-header patterns now matches its Chinese
equivalent(s) (技能/专业技能, 项目/项目经历, 工作经验/工作经历/从业经历, 教育背景/学历), plus a
bilingual form stating both languages on one line (e.g. "Skills · 技能"), common on HK bilingual
resume templates. Two new regression tests (`test_t1_12_chinese_section_headers_...`,
`test_t1_12_bilingual_section_headers_...`).

**`cli.py`'s report crashed outright on a CJK or emoji candidate name under a legacy console
encoding.** Reproduced: `UnicodeEncodeError` under simulated Windows cp1252, aborting the whole
report mid-batch. **Fixed:** `main()` now reconfigures `sys.stdout` with `errors="replace"` so an
unencodable character degrades to `?` instead of crashing the process.

**`cli.py`'s report could have a candidate label forge an extra, convincing-looking row.** A
label containing a newline plus text shaped like a table row (e.g. from a future real Email/Teams
adapter's message-envelope display name -- the current local-folder stub derives labels from
filenames, which can't contain newlines, so this isn't reachable today, but the field is
documented as eventually coming from untrusted envelope data) rendered as a second, standalone
entry. **Fixed:** newlines are stripped from the label at the point `_print_report` builds each
row.

**`jrp_config.py` had the same "parses fine, crashes later mid-scoring" gap round 2 already fixed
for sibling fields, missed for two others.** `required_education_level: 5` (non-string) crashed
with an unrelated `AttributeError` (`'int' object has no attribute 'upper'`); `required_skills:
[123, 456]` (non-string elements) loaded with zero validation and crashed later, mid-scoring, the
moment skill-ontology matching called a string method on one. **Fixed:** both now raise a clean
`JRPConfigError` at load time.

**`channel_adapters.py` had a second TOCTOU race, one level up from the one round 2 fixed.** Round
2 wrapped the per-*file* read in `try/except OSError`; nothing guarded the folder-level
`exists()`-then-`iterdir()` gap. Reproduced: the watched folder vanishing between those two calls
(a concurrent cleanup job, an unmounted network share) raised an uncaught `FileNotFoundError` out
of `fetch_new_submissions()`. **Fixed:** the listing itself is now wrapped the same way, treating a
vanished folder as "no new submissions this cycle."

**The `ai_content`/`fairness_compliance` architectural-invariant test could be defeated by
`dataclasses.replace`.** `test_ai_content_never_constructs_a_score` was a literal `"Score("`
substring search. Confirmed: `dataclasses.replace(score, total_score=100.0, tier=Tier.HIGH_MATCH)`
genuinely builds a manipulated `Score` (executed: LOW_MATCH/12.0 -> HIGH_MATCH/100.0) while
containing zero occurrences of the text `"Score("` -- a green build on code flatly violating FR-9.
There was also no equivalent check at all for `fairness_compliance`, despite `explainability.py`
being equally documented as read-only. **Fixed:** rewrote the check to be AST-based, flagging both
direct `Score(...)`/`x.Score(...)` calls and any `dataclasses.replace(...)` call whose keyword
arguments touch a Score-specific field name (`total_score`, `passed_must_have`,
`failed_must_have_labels`, `scoring_engine_version`) -- narrow enough to not false-positive on this
package's own legitimate `dataclasses.replace` uses on unrelated types (`AccessRequest`,
`ConsentRecord`) or on ordinary string `.replace()` calls, both confirmed via dedicated tests
against the checker itself. Added the missing `fairness_compliance` equivalent.

**Also fixed:** `cli.py`'s report displayed `total_score` at 1 decimal, so a value like 79.95
(correctly `mid_match`) could print as "80.0" sitting next to `mid_match*`, looking like a tier-
classification bug on a skim -- now displayed at 2 decimals, matching `engine.py`'s own rounding
precision.

**Findings deliberately documented rather than code-patched this round** (real, demonstrated, but
either a bigger design change than this pass's scope or a genuine judgment call -- same category as
`anchoring.py`'s hallucination gap):
- `fairness_compliance.SkillOntologyRepository` is a live, unversioned, mutable object designed to
  be wired directly into `ScoringEngine` by reference (T4.13). Confirmed: mutating it via its
  normal `add_synonym_group()` API between two identical `score()` calls (same profile/JRP/
  versions) changed `total_score` from 0.0 to 100.0 with nothing on `Score` recording which
  ontology snapshot produced it (unlike `jrp_version`/`scoring_engine_version`/`parser_version`) --
  contradicting `engine.py`'s own "pure function" docstring. A real fix means either versioning the
  ontology and stamping that version on `Score` (more model churn, on top of this session's
  `failed_must_have_labels` change) or freezing/snapshotting the ontology per scoring run; deferred
  as a genuine design decision rather than rushed.
- The "raw resume text never reaches an LLM" guarantee (FR-9/module-3 doc) is comment-only for
  `ai_content/llm_provider.py`, not code-enforced the way the `Score`-construction wall is --
  confirmed a `TemplateLLMProvider` fed a `SourcePassage` built from raw injected text will happily
  embed it verbatim. Extending architectural-invariant enforcement to this input-flow direction
  (as opposed to the output-flow check just strengthened above) is a larger design task.
- `governance_audit/sqlite_audit_log.py` has no schema versioning (no `PRAGMA user_version`, no
  migration path) -- `CREATE TABLE IF NOT EXISTS` is a silent no-op against a pre-existing file, so
  a future column addition would break every previously-created database file the moment
  `record()` is next called against it. Not a bug today (no column has actually changed yet); a
  forward-looking gap, tracked here rather than built speculatively.
- A handful of narrower test.md coverage gaps (T7.5's injection audit event logging the matched
  regex pattern rather than the flagged content -- arguably the safer design, not necessarily a
  defect; T1.8/T7.4's assertions checking less than what test.md's row promises; no test chaining a
  failed-must-have `Score` into `ai_content`/`cli.py`'s disqualified-row marker end-to-end; two
  must-have criteria sharing one `.label` but failing for different reasons rendering
  indistinguishably as `"FAIL: X; X"`) -- noted for a future test-hardening pass rather than
  addressed individually here.

272 tests (261 -> 272; eleven new regression tests); ruff/mypy clean.

## Real-resume test (2026-07-23): comma-separated skills scored 0% despite the candidate having
## every required skill

The user supplied a real, downloaded "Software Engineer Resume.pdf" (a generic template-style
resume) to run through the pipeline -- not a synthetic fixture. Its Skills section is one
comma-separated line: `C, Java, Sdlc, Software Development, Linux, C#, Communication Skills`.
Extraction kept this as a single, unsplit list item (`_extract_list_field` only ever split on
newlines). Scored against `required_skills=("Java", "C#", "Linux")` -- all three genuinely listed
-- `total_score` came back **0.0**: exact skill-name matching (both `IdentitySkillOntology` and
`SynonymMapSkillOntology` require normalized *equality*, never substring/fuzzy matching) can never
match a required skill against a whole unsplit line.

Comma-separated skill lists are, if anything, more common in real resumes than one-skill-per-line
-- this isn't a rare template quirk. **Fixed:** `extraction.py` gained a dedicated
`_extract_skills_field` (skills only, not projects) that splits each line on commas as well as
newlines. Projects deliberately keep the old newline-only splitting: a project bullet routinely
contains commas within its own prose (e.g. "Led a team of 5, delivering 2 weeks early"), and
comma-splitting there would fragment one project into meaningless pieces. Re-ran the exact real
file after the fix: `total_score` went from 0.0 to 100.0 for the same required skills.

**Follow-up, on request:** the category-label case above was then fixed too, rather than left as a
standing limitation. `test_real_world_resume_unrecognized_headers_are_absorbed_by_previous_
section`'s real-world fixture has a skills line with a category-label prefix ("Programming
Languages: C++, Python, JavaScript") -- comma-splitting alone gave `["Programming Languages:
C++", "Python", "JavaScript", ...]`, individually matchable except that "C++" stayed glued to its
label. Added `_strip_category_label()`: everything up to the first colon in a skills line is
dropped before the comma-split runs, since a colon in a skills line is used almost exclusively for
a category label ("Languages:", "Tools:", "Frameworks:"), never as part of an actual skill name.
`"Programming Languages: C++, Python, JavaScript"` -> `["C++", "Python", "JavaScript"]`, all three
individually matchable. A line with no colon (e.g. "Chinese (Fluent), English (Intermediate)") is
untouched.

**Also fixed, on request, at a deliberately narrow scope:** this same real file has its contact
block (name/email/phone/location) at the very end of the document, after the last recognized
header (Education), with no closing header of its own -- `_split_sections` absorbs everything to
end-of-document into whatever section preceded it, so the extracted "education" field ended up
with the candidate's contact details appended. Doesn't affect scoring (degree-level detection just
looks for keywords like "bachelor" anywhere in the text) or must-have gating, so this is a
data-hygiene issue, not a correctness one. **Fixed:** `_drop_contact_info_lines()` filters any
line matching a high-precision email pattern or a whole-line phone-number pattern (>=7 digits,
only digits/`+()-.` characters) out of every section's captured text, not just the last one --
an email or phone number is never legitimate Skills/Experience/Education content, so this is safe
regardless of where such a line lands. Deliberately does NOT try to strip a bare name or city
("Jenny Ashcroft", "Los Angeles, CA" both still remain in the real file's `education` field after
this fix) -- neither is reliably distinguishable from real section content with a comparably
high-precision pattern, and chasing that would risk stripping legitimate short lines elsewhere;
left as a known, accepted remainder, same judgment-call standard as the "Programming Languages:"
prefix case above.

286 -> 292 tests; ruff/mypy clean.

## Second real-image test (2026-07-23): confidence scoring was a pure length heuristic, blind to
## whether OCR actually produced coherent text

The user supplied a second real file, a downloaded resume *template image* (a dense two-column
design with a photo, icon-labeled contact fields, and a colored sidebar). OCR on it was, as
expected, poor -- this matches the already-documented local-Tesseract accuracy tradeoff -- but the
real finding is what the pipeline did with a *bad* OCR result: "WORK EXPERIENCE" happened to OCR
correctly as a header, and everything after it OCR'd into unreadable garbage ("08 Posmon Tus (c)
sh mma ce..."). `_confidence_for()` only ever checked `len(section_text) >= 10`, so this garbage
field came back `VERIFIED`, confidence `0.95`, `meets_must_have_confidence=True` -- exactly as
trusted as clean text. SOP 2.1.1's own confidence gate ("any field used by a must-have criterion
below 85% confidence must not enter gating, routed to manual review instead") existed specifically
to catch this and never fired, because nothing fed it a real quality signal.

**Fixed:** `ocr.py`'s `extract_text()` now returns `(text, confidence)`, where `confidence` is
Tesseract's own average per-word recognition confidence from `pytesseract.image_to_data()` (0-1,
rescaled from Tesseract's native 0-100) -- not a length guess. Measured directly against both real
files: ~0.41 average confidence on the garbled two-column template vs. ~0.95 on a clean
single-column synthetic fixture and ~0.93-0.94 on the existing clean-layout regression fixtures --
a wide, reliable margin either side of the 0.85 must-have threshold. `pdf_text.py`'s `extract_text
()` now returns the same `(text, confidence)` shape throughout: `1.0` for a real PDF's text layer
or the plain-text passthrough (both deterministic, not a probabilistic guess -- there is no
"OCR-style" uncertainty to signal there), or OCR's real confidence when the submission is an
image. `gateway.py` threads this confidence value from `extract_text()` into `ExtractionService.
extract(text, ocr_confidence)`, and `_confidence_for()` now returns `min(length_based,
ocr_confidence)` when an OCR confidence is present, capping the old length-only heuristic rather
than replacing it (a one-character match is still less trustworthy than a full paragraph, even
from a perfectly-OCR'd image). `ocr_confidence` defaults to `None` for every caller that already
passes plain text directly (all of `ai_content`'s and `scoring_engine`'s existing tests) --
completely unaffected, since `None` means "no OCR involved, use the length heuristic exactly as
before."

Deliberately a document-level average, not per-section: attributing individual OCR word
confidences back to whichever *section* they landed in would need real word-level position
tracking threaded through `_split_sections()`, a materially bigger change than this fix. A single
whole-document average is coarser but correctly catches the demonstrated failure mode (the whole
image was poorly OCR'd, not one isolated section) -- revisit only if a real example demonstrates
one section being unreadable while others are fine on the same document.

Re-ran the real template file through the actual `IngestionGateway` end to end after the fix:
before, it would have silently produced a `VERIFIED`/high-confidence `Score` input from garbage
text; after, it correctly routes to the manual-review queue with `LOW_CONFIDENCE_MUST_HAVE`.

294 tests (290 -> 294: two new `ocr.py` tests for the confidence signal on real images, one
`extraction.py` test proving the cap works with a synthetic garbled-but-long section content, kept
deterministic rather than depending on Tesseract's exact real-world output); five existing OCR/
pdf_text tests updated for the new `(text, confidence)` return shape; ruff/mypy clean.

## Module 5, first slice (2026-07-23): comparison table + drill-down dashboard

Module 5 (Presentation Layer) was entirely "Not Started" until now. Per the user's own
prioritization (Module 5 has 11 checklist items -- notification cards, dashboard overview/
filtering/drill-down/visualizations, JRP configuration UI, fairness-flag review, Pass/Reject +
decision logging -- too large for one increment), this first slice is deliberately scoped to just
the comparison table and candidate drill-down, both read-only.

**What's built:** `presentation/dashboard_data.py` (Streamlit-free: wraps the shared pipeline
runner plus Module 3's `ContentGenerationService` per candidate into a `DashboardRow` -- score,
extracted resume, and generated summary/questions/red-flags together) and `presentation/app.py`
(the Streamlit UI: a `Run` form taking a resumes folder + JRP YAML path, a comparison table, and a
`selectbox`-driven drill-down showing the full matching analysis, summary, interview questions,
and red flags for one candidate at a time). `presentation/launcher.py` binds to `127.0.0.1` only,
same fix as `jrp_editor/launcher.py` (see the Security review section above for why).

**Refactor along the way:** `cli.py`'s `run()` function and the dashboard both need to run the
same Modules 1+2 pipeline (channel adapter -> extraction -> dedup -> profile adapter -> scoring).
Rather than duplicate that wiring in a second entry point, it's now factored into
`src/hr_digital_employee/pipeline.py` (`run_pipeline()` returning `CandidateResult` records, plus
a shared `candidate_label()` helper). `cli.py`'s `run()` is now a thin wrapper mapping
`CandidateResult` down to the `(label, Score)` tuples its own report printer expects --
`tests/integration/test_cli.py`'s existing assertions against `run()`'s public contract needed no
changes.

**A real bug found while building this, not planted by a review round:** `AppTest`-testing the
dashboard's "bad JRP path" error case showed the error banner never appeared -- `load_jrp_from_yaml
()` raised an uncaught `FileNotFoundError` for a missing/unreadable file, since it only ever wrapped
YAML-syntax errors, not the file read itself, in `JRPConfigError`. `cli.py`'s `main()` only catches
`JRPConfigError`, so this was already a live bug there too (a typo'd `--jrp` path crashes with a raw
traceback) -- just never exercised by an existing test. **Fixed:** `path.read_text(...)` is now
wrapped in its own `try/except OSError`, raising `JRPConfigError` the same way the YAML-parse
failure already does.

**What this slice deliberately does NOT cover** (real gaps, not oversights -- see module-5 doc §7
for the authoritative checklist):
- No filtering of any kind (by score, skill, experience, source) -- design.md §3.8 requires that
  filtering never function as an implicit "hide below X%" rejection; the simplest way to guarantee
  that for now is not building filtering yet at all, rather than building it and then having to
  prove a negative.
- No dashboard-level pipeline-overview stats (totals, average score, stage distribution) or
  skill-gap visualizations.
- No Pass/Reject action or decision logging -- design.md §3.8 calls this "the only component with
  a write path to candidate status," which is a real architectural commitment (needs a persistent
  candidate-status store that doesn't exist anywhere in this codebase yet) deserving its own
  increment, not something to bolt on inside this one.
- No persistent candidate store at all: every dashboard run re-executes the full pipeline against
  whatever's currently in the given resumes folder, in memory, same as `cli.py`. Nothing is saved
  between runs.
- The original resume file itself isn't shown in the drill-down, only Module 1's already-extracted
  structured fields (skills/projects/experience/education) -- module-5 doc's "original resume"
  wording is only partially satisfied.
- JRP configuration is not merged into this dashboard; `jrp_editor/` remains a separate tool.

## What this draft does NOT cover yet

This is a rough first draft of Wave 1 (Module 1: Intake & Extraction, the minimum of Module 7:
Governance & Audit needed for Module 1 to log through it), Wave 2's Module 2: Scoring Engine
(must-have gating, weighted/curve-adjusted dimension scoring, tier classification, JRP versioning +
audit logging — all deterministic, no LLM/agent input anywhere in the module, per FR-9), a
YAML-config JRP loader and command-line bridge (`hr-digital-employee`) tying Modules 1 and 2
together end to end, and Wave 3's Module 3: AI-Assisted Content Generation (summary generation with
sentence-level anchoring, interview questions, red-flag detection — architecturally isolated from
scoring per FR-9, enforced by `tests/test_architectural_invariants.py`) and Module 4: Fairness &
Compliance (four-fifths adverse-impact testing with statistical corroboration, skill-ontology
maintenance, consent capture, retention-eligibility checks, explainability, an access/correction
request workflow).

**Not yet built:** manual-review SLA monitoring/alerting, incident routing, weekly operational
review, Talent Pool Store, Candidate Feedback storage, one-round-one-version enforcement, the
NFR-6 rollback hook, the quarterly/on-change fairness re-test scheduler, jurisdiction detection,
real candidate-data-store fulfillment for access/correction requests, most of Module 5 (see its own
section above for the one slice that is built -- no notification cards, no pipeline-overview
stats/filtering/visualizations, no JRP-config-in-dashboard, no Pass/Reject action, no persistent
candidate store, no API server), and Module 6 entirely (empty placeholder package only, per
`md/prompt.md` §5's repository layout). See `md/progress.md` for the authoritative checklist.

## Security + logic review, round 6 (2026-07-23): three more real bugs found and fixed

Two parallel reviews (Module 5's presentation layer, specifically targeted since it's the newest
code and had only been manually smoke-tested; Module 6/7 plus a cross-module `AuditLog` usage
grep), each finding verified against the real code (one via Streamlit's `AppTest`, reproducing the
rendered proto directly) before fixing. Also found while building the reference sample run
documented in the SOP's new Appendix A (see below): actually running realistic resumes through the
CLI, not just synthetic test fixtures, surfaced a bug none of the previous five review rounds'
fixtures happened to trigger.

**1. (High, cross-cutting) `RawSubmission.display_identifier` never fell back to `candidate_name`,
only email/phone/`"unknown"`.** `LocalFolderChannelAdapter` -- the only channel adapter built so
far -- never populates email/phone, only `candidate_name` (the filename). Every manual-review-queue
entry and every audit event referencing a local-folder submission therefore showed the literal
string `"unknown"` instead of an identifier HR could act on, in `cli.py`'s report, the Module 5
dashboard's manual-review list, and `text_extraction_log.py`'s log headers alike -- found
independently by both review rounds above, and by manually running four realistic resumes through
the CLI (see Appendix A: one candidate legitimately routed to manual review printed as `"unknown"`
instead of its filename). The existing test for this property (`test_models.py`) only ever
constructed submissions with `candidate_name=None`, so this exact realistic shape -- name set, no
email/phone -- had never been exercised. **Fixed:** `display_identifier`
(`intake_extraction/models.py`) now falls back through email -> phone -> name -> `"unknown"`; added
`test_display_identifier_falls_back_to_name_for_local_folder_style_submissions` alongside the
existing fallback test.

**2. (Medium-High) A blank "Resumes folder" field in the Module 5 dashboard silently scanned the
process's working directory instead of erroring.** `Path("")` resolves to `.`, which always
`exists()`, so `presentation/app.py`'s unvalidated `st.text_input` let `LocalFolderChannelAdapter`
happily ingest and score whatever unrelated `.pdf`/image files sit in the launch directory as
pseudo-candidates, with no indication the field was ever empty -- confirmed directly. The JRP path
input already fails cleanly here (`JRPConfigError`); only the resumes-folder input lacked equivalent
validation. **Fixed:** a blank value now shows "Resumes folder is required." before any pipeline
run; a non-blank but non-existent path now shows "Resumes folder not found: ..." instead of
whatever `OSError` happened to surface partway through the pipeline. Two new regression tests in
`tests/presentation/test_app.py`.

**3. (Medium) The candidate drill-down's overall-score `st.metric` colored every tier's delta green
with an "up" arrow, including Low Match.** `st.metric(..., delta=tier_label)` defaults an
unrecognized (non-numeric, no leading `-`) delta string to `direction: UP, color: GREEN` --
confirmed directly by inspecting the rendered proto for a Low Match candidate. A tier label isn't a
change-over-time value in the first place, so the worst possible tier rendered with the same
positive-looking indicator as the best one, on the one screen HR is meant to use to judge standing.
**Fixed:** `delta_color="off"` (`presentation/app.py`), confirmed via the proto now reading
`color: GRAY` regardless of tier. One new regression test.

284 tests (280 -> 284: four new regression tests, one existing test extended in place); ruff/mypy
clean.

**Findings documented rather than code-patched this round** (real, verified, but each a bigger
design change than a quick fix -- same category as the ontology-versioning/LLM-input-flow gaps
above):
- `jrp_editor/app.py`'s "Save YAML" button writes directly via `Path.write_text`, with zero call
  into `JRPRepository`/`AuditLog` anywhere in `jrp_editor/` -- confirmed via a repo-wide grep,
  `JRPRepository` is referenced only in its own module and one docstring. SOP 2.2.5 ("every change
  to weights or thresholds is logged: who, when, why") is correctly implemented by
  `JRPRepository.save()`, but it's dead code with respect to the only real HR-facing JRP-editing
  tool that exists today -- every real weight/must-have edit currently produces zero audit trail.
  A real fix means routing the editor's save path through `JRPRepository` (which needs a
  `jrp_id`/version/actor/reason the current one-page form doesn't collect yet), not a one-line
  patch.
- `presentation/app.py`'s dashboard constructs a fresh `InMemoryAuditLog()` per "Run" click,
  passed into the pipeline, then never stores or exposes it -- every dashboard-driven run's entire
  audit trail (manual-review routing reasons, processing events) is generated and immediately
  discarded when the object goes out of scope, unlike `cli.py`'s explicit `--audit-db` flag for the
  same data. This undercuts SOP 1.6's traceability principle for what is likely to become HR's
  primary interactive tool. A real fix needs a persistence/wiring decision (a shared `--audit-db`-
  style option, or a session-level `SqliteAuditLog`), not just a variable move.
