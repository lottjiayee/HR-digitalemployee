# HR Digital Employee — Development Progress

**Last updated:** 2026-07-23
**Source docs:** [requirement.md](./requirement.md), [design.md](./design.md), [modules/](./modules/)

Status values used throughout: `Not Started` → `In Progress` → `Blocked` → `Done`

---

## 1. Overall Module Status

| # | Module | Status | Open items (see §2 — stubbed in code, not blocking) | Module doc |
|---|---|---|---|---|
| 1 | Intake & Extraction | In Progress — core pipeline built, rough draft | Real channel integration and structured-field splitting still stubbed (PDF byte-to-text extraction is real via `pypdf`; image OCR is real via local Tesseract, cloud OCR not chosen); malware scan and 200-resume validation not started | [module-1-intake-extraction.md](./modules/module-1-intake-extraction.md) |
| 2 | Scoring Engine | In Progress — core scoring math + Module 1 adapter built, rough draft | Module 1 -> Module 2 profile adapter is a regex-heuristic stub (word-form numbers, open-ended date ranges not handled); skill ontology is an exact-match/synonym-map stub pending Module 4; one-round-one-version enforcement and NFR-6 rollback hook not started | [module-2-scoring-engine.md](./modules/module-2-scoring-engine.md) |
| 3 | AI-Assisted Content Generation | In Progress — summary/questions/red-flags built, rough draft | 2nd LLM provider not chosen (stubbed with a deterministic offline template); hallucination-rate suspension threshold not defined (no agreed figure exists yet) | [module-3-ai-content-generation.md](./modules/module-3-ai-content-generation.md) |
| 4 | Fairness & Compliance | In Progress — adverse-impact testing + core services built, rough draft | Jurisdiction *detection* not built (default-to-strictest rule is); quarterly/on-change re-test scheduler and retention scheduler not started (need Module 7's job infrastructure); access/correction requests are a workflow skeleton (no real candidate-data store to fulfill against yet) | [module-4-fairness-compliance.md](./modules/module-4-fairness-compliance.md) |
| 5 | Presentation Layer | In Progress — comparison table + drill-down dashboard built, rough draft | Notification cards, pipeline overview/filtering, skill-gap visualizations, fairness-flag review UI, and the Pass/Reject action + decision logging are all not started | [module-5-presentation-layer.md](./modules/module-5-presentation-layer.md) |
| 6 | Scheduling Coordination | Not Started | Manus scope confirmation pending (stubbed) | [module-6-scheduling-coordination.md](./modules/module-6-scheduling-coordination.md) |
| 7 | Governance & Audit | In Progress — audit log interface + persistence | AuditEvent/AuditLog built, with both in-memory and SQLite-backed implementations; SLA monitoring, talent pool, feedback storage, retention all not started; named owner not assigned | [module-7-governance-audit.md](./modules/module-7-governance-audit.md) |

**Rough-draft code exists** as of this update: `src/hr_digital_employee/` (Python), covering Module
1's full pipeline (channel adapters — now also picking up image files, not just PDFs — real PDF
text extraction via `pypdf`, local image OCR via Tesseract, injection screening, structured-field
extraction, dedup, manual review queue, gateway orchestrator — the gateway now audit-logs every
manual-review routing reason, not just suspected injection, and optionally appends every
successfully-extracted submission's raw text to a persistent `TextExtractionLog`), Module 2's
scoring math (must-have gating, Linear/Step/Buffered curves, weighted dimension scoring + tier
classification, JRP data model + weight-template presets + audit-logged versioning, a skill-ontology
consumption point), a regex-heuristic Module 1 -> Module 2 profile adapter connecting the two
(`scoring_engine/profile_adapter.py`), and Module 7's `AuditEvent`/`AuditLog` interface with both an
in-memory and a SQLite-backed implementation (the latter survives a process restart; still a
temporary/local-only bridge, not the real deployment data store — see ASSUMPTIONS.md). Modules 1
and 2 are now connected end to end: `tests/integration/test_intake_to_scoring_pipeline.py` runs a
real resume through `IngestionGateway.run_once()` and into `ScoringEngine.score()` and checks a real
`Score` comes out, not just hand-built `CandidateProfile` fixtures.

There is now also a way to actually *run* this rather than only read its tests: `scoring_engine/
jrp_config.py` loads a JRP from a YAML file (weights can be omitted per-criterion to fall back to
the chosen weight template's preset), and the `hr-digital-employee` console script (`cli.py`,
registered in `pyproject.toml`) points at a resumes folder + a JRP YAML file and prints a ranked
scoring report end to end. This is a temporary command-line bridge, not Module 5's real dashboard/
JRP-config UI (still Not Started) — see ASSUMPTIONS.md.

There's now also a form over that YAML file instead of hand-editing it: `jrp_editor/` is a one-page
Streamlit app (`hr-digital-employee-jrp-editor` console script, optional `ui` extra) where HR fills
in weights/must-haves/curves and gets a live weight-sum check and the same `JRPConfigError`
validation the CLI enforces before saving. Still not Module 5's real JRP configuration UI — no
auth, no history, not embedded in a dashboard — see ASSUMPTIONS.md.

Wave 3 is now drafted too: Module 3's `ContentGenerationService` (`ai_content/`) generates a
factual candidate summary with every sentence verified against a Module 1 source passage before
being kept (FR-10; a fabricated/unanchored sentence is dropped, proven with a fake LLM provider
that deliberately hallucinates one), three-angle interview questions targeted off Module 2's score
breakdown, and red-flag detection (inconsistent dates, keyword stuffing, frequent job changes,
employment gaps — the latter two worded as neutral clarification prompts, never a penalty, per
fairness guidance). Module 4's fairness/compliance services (`fairness_compliance/`) cover
four-fifths adverse-impact testing corroborated by a two-proportion significance test, skill-
ontology maintenance (structurally satisfying Module 2's `SkillOntology` protocol with **zero
import dependency on `scoring_engine`**), consent capture (talent-pool consent kept separate from
application consent), retention-eligibility checks, explainability-on-request (reads an existing
`Score` only, never re-scores), and an access/correction request workflow. `tests/
test_architectural_invariants.py` enforces FR-9's determinism wall by AST-checking imports:
`scoring_engine` may never import `ai_content` or `fairness_compliance`, and `ai_content` may never
construct a `Score`.

254 tests, mypy --strict / ruff / ruff format all pass (OCR tests skip gracefully on a machine
without the Tesseract binary). See `ASSUMPTIONS.md` at the repo root for every stub this draft
makes — including an observed, non-theoretical accuracy tradeoff for local OCR vs. a managed cloud
provider. Module 6 is an empty placeholder package only; Module 5 has the CLI bridge above as a
temporary stand-in for its real UI.

**2026-07-21 code-review pass:** found and fixed two gateway-level correctness bugs (not stubs —
actual defects) via a Standards/Spec code review against design.md/FR-3: (1) a resume whose Skills
or Experience section was missing entirely (`UNVERIFIED`, not just low-confidence) was silently
processed instead of routed to manual review; (2) `LocalFolderChannelAdapter` re-returned every
file on every call instead of only new ones since the last fetch, so a real polling loop would
reprocess the same resumes forever. Also: untrusted raw text is now logged to `TextExtractionLog`
only after injection screening (previously logged before), and a handful of smaller Standards-axis
smells (duplicated identity-fallback logic, a query function with a hidden global side effect,
a magic version string) were cleaned up. See `ASSUMPTIONS.md` for the per-fix writeups.

**2026-07-22 code-review pass (Modules 3+4):** found and fixed four real defects via a Standards/
Spec review against design.md/prompt.md before committing: (1) `adverse_impact.four_fifths_test()`
produced zero audit events at all, violating md/prompt.md §2 invariant 5 ("every fairness flag"
must be audit-logged) — added `AdverseImpactTestingService` to close the gap; (2) the same function
force-flagged a JRP with zero hires in every group as maximal adverse impact, since dividing by a
zero highest-rate was hardcoded to 0.0 rather than treated as "no disparity observed"; (3)
`interview_questions.generate_interview_questions()` could produce zero VERIFICATION and zero GAP
questions for any candidate scoring in the (0.5, 0.85) band on every dimension — not a rare edge
case, since that band covers the entire Mid Match tier — fixed with a relative-rank fallback so
every candidate gets at least one of each angle; (4) `fairness_compliance/explainability.py`
imported `Score` via `scoring_engine.interfaces` but `JRP` via `.models` directly, and
`ai_content/interview_questions.py` did the same for `Dimension` — both now go through
`.interfaces` consistently (and `Dimension` was added to that module's public exports, since a
downstream consumer needed it). See `ASSUMPTIONS.md` for the write-ups, including two
findings resolved by documenting an interpretation rather than changing code (only the summary
routes through `LLMProvider`, not interview questions/red flags; a small regex is deliberately
duplicated across `ai_content` and `scoring_engine` rather than shared, to keep them decoupled).

**2026-07-22 test-coverage check (Modules 3+4):** audited the new test suites against every
`test.md` §3/§4 scenario line-by-line. Coverage was already solid (T3.1-T3.6, T3.8, T4.1-T4.2,
T4.5-T4.8, T4.11-T4.13 all directly exercised); T3.7's injection-defense scenario turned out to
already be covered end-to-end by Module 1's `test_t1_11_suspected_injection_is_flagged_logged_and_
routed_not_scored` (a resume that fails injection screening never reaches Module 3 at all, so there
was nothing left for this module to test). Closed three real gaps: (1)
`standardized_difference_test`'s `standard_error == 0` guard was never exercised by any test — added
both-groups-at-0% and both-groups-at-100% cases; (2) T4.4 ("fairness output is aggregate-only, no
individual's protected attributes exposed") had no explicit assertion — added a structural test on
`FourFifthsResult`'s fields; (3) `TemplateLLMProvider`'s generic-field fallback sentence (for a
field name outside skills/projects/experience/education) was unreachable dead code from every
existing test, since `build_source_passages` never emits one — added a dedicated
`tests/ai_content/test_llm_provider.py` testing the provider in isolation rather than only through
the summary-generation pipeline. 205 -> 211 tests; no production code changed.

**2026-07-22 security review:** found and fixed two real vulnerabilities (see ASSUMPTIONS.md for
full write-ups). (1) The new JRP editor's Streamlit server bound every network interface by
default with no authentication in front of its arbitrary-file-path Load/Save fields — confirmed via
its own startup banner printing a LAN/public URL alongside the local one; fixed by binding
`launcher.py` to `127.0.0.1` explicitly. (2) A resume submitted as an image with a header declaring
far more pixels than its actual data backs up crashed the entire intake batch uncaught
(`PIL.Image.DecompressionBombError` wasn't among `ocr.py`'s caught exceptions) — the same untrusted-
input threat model `injection_screening.py` already defends against, with an image-based angle left
open; fixed by routing it through the existing "unparseable -> manual review" path every other
malformed file already takes. 222 -> 223 tests.

**2026-07-22 security + logic review, round 2:** three parallel reviews (intake/CLI/JRP-editor,
scoring engine, AI-content/fairness), each verifying findings by actually running the real code.
Found and fixed 7 more real bugs (full write-ups in ASSUMPTIONS.md): a missing exception boundary
in `gateway.py` that let one bad submission crash the whole intake batch; a case-sensitive-glob bug
that silently dropped any resume with an uppercase extension (`Resume.PDF`) with no audit trail; a
TOCTOU race in the local-folder channel adapter; a JRP YAML's `minimum_years`/`tier_thresholds`/
`required_skills` each being able to parse successfully but then either crash later mid-scoring or
silently produce a wrong score, instead of a clean `JRPConfigError` at load time; and overlapping/
concurrent job-date ranges being double-counted (`profile_adapter.py`) or misread as a false gap
(`red_flags.py`), plus a reversed/typo'd date range fabricating a gap in both. One further finding
-- `ai_content/anchoring.py`'s one-directional coverage check can be defeated by a sentence padding
a passage's real keywords with fabricated content -- was investigated but deliberately *not*
code-patched: measured that a naive bidirectional-threshold fix can't actually distinguish this from
legitimate LLM paraphrasing (a genuine paraphrase's own coverage ratio measured lower than the
attack's), so it's documented as a confirmed, demonstrated gap needing real semantic verification
rather than a heuristic that would create false confidence. 223 -> 235 tests; ruff/mypy clean.

**2026-07-22 security + logic review, round 3:** four parallel reviews covering
dedup/extraction/review-queue, scoring-engine internals, ai_content/fairness_compliance internals,
and jrp_editor+cli+governance_audit, every finding verified by running the real code (including the
JRP editor's UI, via Streamlit's `AppTest`). Found and fixed 13 more real bugs (full write-ups in
ASSUMPTIONS.md) -- the two most consequential: (1) `dedup.py` used to auto-merge two different real
candidates who happened to share an exact full name with no other identifying info, silently, with
no human ever seeing it; (2) the JRP editor's per-dimension widgets used a fixed Streamlit `key=`,
so loading a file or switching weight templates showed a green success message while every widget
kept silently displaying the *previous* JRP's stale values underneath -- HR would have been editing
the wrong data with a false-positive confirmation telling them otherwise. Also fixed: a prose
sentence ending in a bare section-header word could steal that section's marker slot in
`extraction.py`; an unbounded hidden-text regex in `injection_screening.py` could strip real,
unrelated resume content between two ordinary style attributes; a forgeable delimiter in
`text_extraction_log.py`; a NaN `years_of_experience` silently poisoning a Score; whitespace and
silent-overwrite bugs in both skill-ontology implementations; a missing version-monotonicity/
atomicity check in `jrp_repository.py`; a self-contradictory interview-question pair; and an
uncaught crash on an incompatible `--audit-db` file. 235 -> 254 tests; ruff/mypy clean.

**2026-07-22 spec revision (Module 2, must-have semantics):** the source SOP blueprint
(`HR_Digital_Employee_Blueprint (2).docx`) was edited to change §2.2.2/§2.2.4: a failed must-have
criterion no longer withholds the weighted score or forces Low Match — it is flagged alongside a
fully-computed score/breakdown so HR sees the whole profile before deciding, never an auto-reject.
Updated to match: `scoring_engine/engine.py`'s `score()` (removed the early-return-with-0.0-score
path; must-have and weighted scoring now both always run), `fairness_compliance/explainability.py`
(the must-have-failure explanation is appended to the full score explanation instead of replacing
it with an empty one), plus `requirement.md` FR-7, `design.md` §3.4, `module-2-scoring-engine.md`,
and `test.md` T2.3/TE2E.2. No other content differs between this SOP revision and the one
`requirement.md`/`design.md` were originally built from (diffed line-by-line). 254 tests still pass
(two rewritten: `test_t2_3_...`, `test_explanation_for_a_must_have_failure_...`); ruff/mypy clean.

**2026-07-22 security + logic review, round 4:** three parallel reviews specifically targeting
regressions from the must-have semantics change above, every finding reproduced before fixing.
Found and fixed 6 more real bugs (full write-ups in ASSUMPTIONS.md) — the most consequential:
`Score.failed_must_have_label` could only ever name the FIRST of several failing must-have
criteria, found independently by two reviews, undercutting the revision's own "HR sees the whole
profile" goal on the same day it was written; renamed to a `failed_must_have_labels` tuple across
`engine.py`/`explainability.py`/`cli.py`. Also fixed: `cli.py`'s ranked report could show a
disqualified candidate at #1 as "high_match" with the disqualification easy to miss on a skim (a
direct regression from the score no longer being forced to 0); a `profile_adapter.py` crash
(`OverflowError`) on an oversized digit run before "years"; `red_flags.py`'s gap/inconsistency
detectors silently dropping every match after the first; `dedup.py` auto-merging two different
people whose phone/email were non-empty punctuation that both normalized to `""`; and
`jrp_editor/app.py`'s must-have table having zero columns on every brand-new JRP. 254 -> 261 tests;
ruff/mypy clean.

**2026-07-22 security + logic review, round 5:** a test-coverage/architectural audit plus two
adversarial sweeps, six more real bugs found and fixed (full write-ups in ASSUMPTIONS.md) — the
most consequential: `extraction.py`'s section headers were English-only, so an identical candidate
scored 60.0/Mid Match with English headers but 0.0/Low Match with Chinese headers, silently
violating SOP 2.1.1's own "identical qualifications, identical outcome regardless of language mix"
guarantee; now recognizes Chinese and bilingual (e.g. "Skills · 技能") headers for all four
sections. Also fixed: `cli.py` crashing on a CJK/emoji candidate name under a legacy console
encoding; a candidate label forging a fake extra report row via an embedded newline; two more
`jrp_config.py` fields (`required_education_level`, `required_skills` elements) that parsed fine
but crashed later mid-scoring instead of raising a clean `JRPConfigError`; a second `channel_
adapters.py` TOCTOU race at the folder level (round 2 only fixed the per-file one); and the
`ai_content`/`fairness_compliance` architectural-invariant test being defeated by `dataclasses.
replace` (a literal `"Score("` substring search missed a genuine `Score` mutation) — rewritten to
be AST-based, and extended to cover `fairness_compliance` too. Three findings documented rather
than code-patched this round (a live/unversioned skill-ontology object that can silently change a
score's outcome between two identical calls; the "raw text never reaches an LLM" guarantee being
comment-only, not code-enforced; `SqliteAuditLog` having no schema-versioning path) — see
ASSUMPTIONS.md. 261 -> 272 tests; ruff/mypy clean.

**2026-07-23 security + logic review, round 6:** two parallel reviews (Module 5's presentation
layer, specifically since it's the newest code and only manually smoke-tested; Module 6/7 plus a
cross-module `AuditLog` usage grep), found and fixed 3 more real bugs (full write-ups in
ASSUMPTIONS.md) -- also surfaced by actually running realistic resumes through the CLI while
building the SOP's new Appendix A reference sample run: (1) `RawSubmission.display_identifier`
never fell back to `candidate_name`, so every manual-review-queue entry and audit event for a
local-folder submission (the only channel adapter built so far) showed `"unknown"` instead of an
actionable identifier; (2) a blank "Resumes folder" field in the Module 5 dashboard silently scanned
the process's working directory instead of erroring; (3) the drill-down's overall-score `st.metric`
colored every tier's delta green with an "up" arrow, including Low Match. Two further findings
documented rather than code-patched (bigger design changes, not quick fixes): the JRP editor's
"Save YAML" button never routes through `JRPRepository`/`AuditLog`, so real weight/must-have edits
today produce zero audit trail; the dashboard's per-run `InMemoryAuditLog` is discarded, not
persisted or exposed. 280 -> 284 tests; ruff/mypy clean.

**2026-07-23: Module 5 first slice -- comparison table + drill-down dashboard.** Built
`presentation/app.py`, a read-only Streamlit dashboard (comparison table across every scored
candidate, per-candidate drill-down with score breakdown/summary/interview questions/red flags),
plus `presentation/dashboard_data.py` (Streamlit-free data layer, same pattern as
`jrp_editor/config_builder.py`) and `presentation/launcher.py` (loopback-only, same fix as
`jrp_editor/launcher.py`). Along the way, extracted `pipeline.py` as the shared Modules-1+2 runner
so `cli.py` and the new dashboard don't each duplicate the intake/scoring wiring; `cli.py`'s public
`run()` contract is unchanged. Building the dashboard's error handling surfaced one more real,
pre-existing bug: `jrp_config.load_jrp_from_yaml()` raised an uncaught `FileNotFoundError` for a
missing/unreadable path instead of `JRPConfigError` -- neither `cli.py` nor the new dashboard
catches anything broader than `JRPConfigError`, so a typo'd path crashed with a raw traceback
either way; fixed to wrap `OSError` the same way YAML-syntax errors already are. 272 -> 280 tests;
ruff/mypy clean; manually smoke-tested by launching the real Streamlit server and confirming it
serves successfully, on top of `AppTest`-driven tests that exercise the actual pipeline run,
drill-down selection, and error path.

**2026-07-23: real-resume test finds a genuine 0-vs-100 scoring bug.** The user supplied an actual
downloaded resume PDF (not a synthetic fixture) to run through the pipeline. Its skills were one
comma-separated line; `extraction.py` only ever split on newlines, so the whole line stayed one
unsplit item and exact skill-name matching could never match a required skill against it --
scoring the same real candidate against `required_skills=("Java", "C#", "Linux")` (all three
genuinely listed) came back **0.0/100**. Fixed with a dedicated skills-only comma+newline split
(kept separate from `projects`, where a bullet's own prose routinely contains commas); re-ran the
real file after the fix and confirmed 0.0 -> 100.0 for the same inputs. Also fixed: the same real
file has its contact block (name/email/phone/city) at the very end of the document with no
closing header, so the email and phone number were being absorbed into the "education" field --
`_drop_contact_info_lines()` now filters email/phone-shaped lines out of every section. On
request, also fixed the category-label case rather than leaving it as a limitation:
`_strip_category_label()` drops everything up to a skills line's first colon before the
comma-split runs, so "Programming Languages: C++, Python, JavaScript" now splits cleanly into
`["C++", "Python", "JavaScript"]` instead of leaving the label glued to "C++". See ASSUMPTIONS.md
for the full write-up, including the one limitation still deliberately left alone (a bare
name/city in a trailing contact block isn't reliably distinguishable from real content, so it
isn't stripped). 286 -> 292 tests; ruff/mypy clean.

**2026-07-23: a second real-image test finds confidence scoring was blind to OCR quality.** The
user supplied a real downloaded resume *template image* (dense two-column, icon-heavy layout).
OCR on it was poor as expected (the already-documented local-Tesseract tradeoff), but the real
finding: `_confidence_for()` was a pure length heuristic, so a section whose header happened to
OCR correctly followed by unreadable garbled content still scored `VERIFIED`/`0.95`/`meets-must-
have-confidence=True` -- SOP 2.1.1's confidence gate, meant to catch exactly this, never fired.
Fixed by wiring Tesseract's own average per-word OCR confidence (via `image_to_data()`) through
`ocr.py` -> `pdf_text.py` -> `gateway.py` -> `ExtractionService.extract()`, which now caps the
length-based confidence with it when OCR was involved (`None` for a real PDF text layer or plain
text, unaffected). Measured directly: ~0.41 confidence on the garbled real file vs. ~0.95 on a
clean one. Re-ran the real file through the actual gateway end to end: it now correctly routes to
manual review (`LOW_CONFIDENCE_MUST_HAVE`) instead of silently scoring on garbage. 292 -> 294
tests; ruff/mypy clean. See ASSUMPTIONS.md for the full write-up.

**2026-07-23 review of the above: one regression found in the new contact-info stripping.**
`_is_phone_like_line()` (added alongside the comma-split/category-label fixes above) flags any
line whose only characters are digits/`+()-. ` with >=7 digits -- but a bare tenure line like
"2019 - 2023" under a job title (a common, legitimate layout) satisfies that same shape (8 digits,
only `-`/space), so it was being silently deleted from the Experience section before
`profile_adapter.py`'s year-range fallback ever saw it. Verified end to end: a candidate with
"Senior Developer at TechCorp / 2019 - 2023 / Led backend development..." scored
`years_of_experience == 0.0` instead of `4.0`, with no error or manual-review flag -- a silent
scoring defect, not a missing feature. **Fixed:** `_is_phone_like_line()` now excludes any line
matching a bare year-range shape (`YYYY - YYYY` or `YYYY - Present/Current`) before the
digit-count check, mirroring `profile_adapter.py`'s/`red_flags.py`'s own `_YEAR_RANGE_PATTERN`
(kept as a separate local copy, consistent with this codebase's existing duplicated-regex
convention -- see ASSUMPTIONS.md). Two new regression tests confirm both the date-range and
open-ended (`- Present`) cases survive, while real phone numbers are still caught. 294 -> 296
tests; ruff/mypy clean.

**2026-07-23 security + logic review, round 7:** four parallel adversarial reviews split by
module (`intake_extraction`; `scoring_engine`; `ai_content`/`fairness_compliance`;
`governance_audit`/`presentation`/`cli`/`jrp_editor`), each agent required to reproduce every
finding by executing the real code, found and fixed 18 more real bugs (full write-ups in
ASSUMPTIONS.md) -- more than any prior round. A Unicode/internationalization cluster (zero-width
characters defeating injection screening, full-width CJK punctuation breaking skills splitting,
NFC/NFD normalization mismatches failing skill-ontology matches, en/em dashes invisible to
date-range parsing, full-width digits breaking phone dedup) was the single largest group, none of
which prior rounds' fixtures happened to exercise. Also fixed: NaN/Infinity bypassing every
numeric-requirement validation in the scoring engine (a config typo could create a permanent,
invisible must-have gate no candidate could ever pass); "Present"/"Current" ongoing roles being
invisible to every red-flag detector; a self-contradicting verification+gap interview-question
pair for mid-range dimensions; a blank JRP must-have label crashing both the CLI and dashboard;
an audit-log write failure crashing an entire processing batch (paired with making
`SqliteAuditLog` detect a genuinely incompatible schema eagerly, at construction, so that fix
didn't silently mask the one scenario that really does need to fail loudly); the dashboard's
candidate drill-down showing the wrong candidate's score when two rows share a label; and
candidate labels not stripping raw ANSI escape sequences (untrusted data could spoof console
output). Two findings documented rather than code-patched: homoglyph substitution still defeats
injection screening (needs a confusables table); word-form date ranges ("2015 to 2020") remain
unparsed. 296 -> 336 tests; ruff/mypy clean.

**2026-07-23: one more real bug found while building the SOP blueprint's Appendix B.** Running an
identical candidate through the pipeline once in English and once in Chinese, to demonstrate the
consistency guarantee for the blueprint document, surfaced a genuine bug:
`profile_adapter.py`'s degree keywords were English-only, so "计算机科学学士" (Bachelor of
Computer Science) scored `EducationLevel.NONE` instead of `BACHELOR` -- the same candidate scored
100.0 in English but 85.0 in Chinese. Fixed by adding Chinese degree-keyword equivalents
(博士/硕士/学士/副学士/高中/中学), with a negative lookbehind so "学士" doesn't match inside
"副学士" (associate degree). 336 -> 341 tests; ruff/mypy clean. The blueprint document itself
(`HR_Digital_Employee_Blueprint (2).docx`) was updated with a new Appendix B verifying this and
two other round-7 hardening scenarios (cross-language/typographic consistency, injection-screening
obfuscation resistance) against the real reference implementation, plus short clarifying notes
added to sections 2.1.1, 2.1.2, and 2.7.3.

**2026-07-23: test-coverage audit finds the dashboard's file-upload path entirely untested.** A
full review of what the input-file/intake path does and doesn't test found one gap bigger than the
rest: `UploadedFilesChannelAdapter` and `build_dashboard_rows_from_uploads` -- the code behind the
dashboard's `st.file_uploader` widgets, which the app treats as the *default* input mode over the
folder-path fallback -- had zero tests; every existing `test_app.py` scenario only drove the
folder-path fields. Closing it required solving a real tooling gap first: Streamlit 1.60.0's
`AppTest` testing harness has no public API to simulate `st.file_uploader`. Resolved by
monkeypatching `streamlit.file_uploader` itself to return lightweight fake files, letting app.py's
real upload-mode branch (temp-file JRP round-trip, scoring, every error path) run end to end
without depending on Streamlit's undocumented internals. Added 13 tests: the adapter and
dashboard-data functions directly, plus five `AppTest`-driven scenarios (successful run,
missing-resumes error, missing-JRP error, invalid-JRP error, uploads correctly overriding stale
folder-path text). No behavior changed -- this was a coverage gap, not a bug. Other gaps found in
the same audit (multi-page PDFs, empty files, unsupported extensions, large-file limits,
non-English/rotated OCR, cross-extension MIME spoofing, Unicode filenames) were deliberately
deferred to a later round. 341 -> 354 tests; ruff/mypy clean.

**2026-07-23: closed the multi-page-PDF gap.** `pdf_text.py` already concatenated every PDF page
correctly, but the only PDF test fixture builder produced single-page PDFs, so nothing ever
verified it. Added a multi-page PDF fixture builder and a regression test confirming every page's
text appears, in page order. No behavior change. 354 -> 355 tests; ruff/mypy clean.

**2026-07-23: closed the remaining input-file audit gaps -- one real bug found and fixed.**
Investigated the six remaining items via real code execution. Found and fixed a genuine bug: a
resume image scanned/photographed sideways or upside down OCR'd into garbage (confidence collapsed
from ~0.93 to ~0.33) because nothing corrected the page's orientation before recognition -- fixed
by running Tesseract's orientation-detection (OSD) pass first and un-rotating the image, verified
correct at 90/180/270 degrees. The other five turned out to already behave correctly, just
untested, and now have regression tests locking that in: empty/zero-byte submissions route to
manual review cleanly; unsupported extensions (.docx/.rtf/no-extension) are silently (and
deliberately) skipped; large submissions (100-page PDF, ~950KB text) extract in well under a
second with no crash; a file's extension can't spoof its real content since dispatch reads magic
bytes, not filenames; Unicode/emoji filenames work correctly. One item remains a genuine open gap:
only the English Tesseract language pack is installed in this environment, so non-English (e.g.
Chinese) resume images would OCR through the wrong language model -- closing that needs installing
additional language data, an infrastructure change rather than a code fix. 355 -> 365 tests;
ruff/mypy clean.

**Note on "Open items":** none of these stop code from being written. §2 below splits every open
item into two kinds: ones an autonomous build can stub behind a clean interface and keep moving
(per prompt.md §3's stub-and-document rule), and ones that are real-world facts no amount of code
can substitute for (who the owner is, whether Legal has signed off) — those only gate **go-live**,
never the build itself. See prompt.md §3 for the authoritative rule if this page and prompt.md ever
seem to disagree — prompt.md's autonomy rule always wins for anything code-related.

---

## 2. Open Decisions

### 2a. Stubbable during the build (code proceeds now; real choice swapped in later)

Per prompt.md §3, an autonomous build stubs each of these behind an interface and records the
assumption in `ASSUMPTIONS.md` — it does **not** wait for an answer. Check off once a real decision
replaces the stub:

- [ ] Cloud platform (design.md §10.1)
- [ ] Second LLM provider for content generation (design.md §10.2) — Module 3 stub
- [ ] Manus's exact API/SDK integration shape (design.md §10.3) — Module 6 stub
- [ ] Tech stack standard beyond "Python" (design.md §10.4)
- [ ] Data residency (design.md §10.5) — storage config stub
- [x] Build vs. buy for PDF byte-to-text extraction (design.md §10.6) — built: `pypdf`
      (`intake_extraction/pdf_text.py`); see ASSUMPTIONS.md
- [ ] Build vs. buy for image OCR (design.md §10.6) — free/offline side built: local Tesseract
      (`intake_extraction/ocr.py`); cloud OCR (Azure AI Document Intelligence/AWS Textract) not
      chosen — observed accuracy gap on real resume layouts, see ASSUMPTIONS.md — Module 1 stub
- [ ] Build vs. buy for structured Skills/Projects/Experience/Education splitting (design.md
      §10.6) — still a regex-heuristic stub, separate decision from the PDF text-extraction one
      above — Module 1 stub
- [ ] Scale expectations / resumes-per-month (design.md §10.7) — affects stub sizing, not correctness
- [ ] ATS/HRIS integration or greenfield (requirement.md §7.1) — integration-point stub
- [ ] WhatsApp in this phase or deferred (requirement.md §7.2) — Module 1 channel adapter stub
- [ ] Google Calendar required or Microsoft-Graph-only (requirement.md §7.3) — Module 6 adapter stub
- [ ] Discrimination-appeal retention window length (module-7 §6) — Module 7 retention-job stub
- [ ] Hallucination-rate suspension threshold (module-3 §6) — Module 3 audit-process stub

### 2b. Not stubbable — real-world decisions that gate go-live, not the build

These cannot be coded around. The autonomous build proceeds without them (the code doesn't need a
named person to exist), but the system should not go live until they're resolved:

- [ ] Named operational owner assigned (requirement.md §7.4)
- [ ] JRP ownership assigned (requirement.md §7.5)
- [ ] Legal/Compliance review of PDPO/GDPR/PIPL sections (requirement.md §7.6)
- [ ] Rollout sequencing: Workflow A before B, or together (requirement.md §7.7)
- [ ] Build vs. vendor vs. buy overall path (requirement.md §7.8) — moot once a build already exists,
      but worth confirming this was the intended path

---

## 3. Module 1 — Intake & Extraction

- [x] Email intake adapter — stub only (`LocalFolderChannelAdapter`, reads a local folder; real Email connector not built)
- [x] Teams intake adapter — same stub covers this (channel is a parameter, not a separate adapter yet)
- [ ] Malware/sandbox scanning — not started
- [x] Local image OCR (JPEG/PNG/GIF/BMP/WEBP) — real Tesseract via `pytesseract`; requires the
      Tesseract binary on the machine; no rasterization of scanned/image-only PDFs (still routes
      to manual review, per FR-4/test.md T1.6)
- [x] Injection screening — heuristic stub (hidden-text stripping + instruction-pattern detection)
- [x] Manual-review queue — in-memory only, no SLA monitoring yet
- [x] Extraction: Skills / Projects / Experience / Education — heuristic stub, not the real parser
- [x] Confidence scoring per field -- length-based, capped by Tesseract's real per-word OCR
      confidence when the source was an image (not a length-only guess for OCR'd content)
- [x] Identity matching & dedup — heuristic name-similarity, not a real fuzzy-match library
- [x] Parser version stamping
- [ ] 200-resume accuracy validation (≥95%) — not started, needs a real annotated dataset

## 4. Module 2 — Scoring Engine

- [x] JRP data model — weights, must-have flags, curves; versioned via `JRPRepository`
- [x] Weight template presets (5 role types, exact percentages) + validation (sum to 100%)
- [x] Must-have gating check — separate `must_have_criteria` list; a failure is flagged alongside
      a fully-computed weighted score (2026-07-22 SOP revision — previously withheld the score)
- [x] Matching curves (Linear/Step/Buffered)
- [x] Skill-ontology-backed matching — consumption point built (`SkillOntology` protocol); real
      ontology table is Module 4's, not built yet (stub-only `IdentitySkillOntology`/
      `SynonymMapSkillOntology` for now)
- [x] Weighted score calculation + normalization
- [x] Tier classification (80%/60% default thresholds, configurable per JRP)
- [x] JRP change audit logging — `JRPRepository.save()` audit-logs actor/reason/version
- [x] Scoring-engine version stamping — every `Score` carries both `scoring_engine_version` and `parser_version` (NFR-5), plus an audit-logged warning (not a hard block) if a JRP's Educational Level weight exceeds the 15% guideline default (module-2 doc §4)
- [ ] One-round-one-version enforcement — not started, needs a hiring-round/Application entity
- [ ] Rollback trigger hook — not started, needs a live metrics feed (NFR-6)
- [x] YAML-based JRP config loader (`scoring_engine/jrp_config.py`) — HR-editable stand-in for
      Module 5's real JRP configuration UI (still Not Started); see ASSUMPTIONS.md
- [x] Module 1 -> Module 2 profile adapter — `profile_adapter.build_candidate_profile()` maps
      `ExtractedResume` -> `CandidateProfile` via regex heuristics (year-phrase/year-range parsing,
      a degree-keyword table); `tests/integration/test_intake_to_scoring_pipeline.py` proves a real
      resume flows from `IngestionGateway.run_once()` through to a `Score` end to end

## 5. Module 3 — AI-Assisted Content Generation

- [ ] LLM provider selected + integrated — stubbed with `TemplateLLMProvider` (deterministic, offline)
- [x] Structured-input-only enforcement — `SummaryGenerationService`/`ContentGenerationService` take only `ExtractedResume` + `Score`, no raw-text parameter exists anywhere
- [x] Summary generation
- [x] Sentence-level anchoring — `anchoring.py`, coverage-based heuristic (judgement call, see ASSUMPTIONS.md)
- [x] Interview question generation — verification/gap angles from `Score.breakdown`, behavioral grounded in real project/experience text when available
- [x] Red-flag detection — inconsistency, keyword stuffing, frequent job changes, employment gap
- [x] Red-flag fairness framing review — gap/frequency flags carry `neutral_framing=True`, worded as clarification prompts (test.md T3.6)
- [x] Model/prompt version stamping — `MODEL_VERSION`/`PROMPT_VERSION` on every `CandidateSummary`
- [x] Hallucination-audit hook — `HallucinationAuditLog.sample()`
- [ ] Hallucination threshold + suspension logic — mechanism built (`is_suspension_triggered`), no default number exists to wire it to yet (see ASSUMPTIONS.md)

## 6. Module 4 — Fairness & Compliance

- [ ] Voluntary demographic collection — `DemographicRecord` modeled; no intake UI/flow to actually collect it yet (Module 5's job)
- [x] Selection-rate calculation — `GroupOutcome.selection_rate`
- [x] Four-fifths rule check — audit-logged via `AdverseImpactTestingService` (every flag *and* every pass, per prompt.md invariant 5)
- [x] Statistical significance corroboration — two-proportion z-test (see ASSUMPTIONS.md for why not chi-square)
- [ ] Pre-deployment back-test — no "deployment"/activation concept exists yet to gate
- [ ] Quarterly re-test scheduler — needs Module 7's job infrastructure (not built)
- [ ] Re-test trigger on JRP weight/must-have change (not calendar-only) — same gap as above
- [ ] Disparate-treatment review workflow — not started
- [x] PICS collection notice — `consent.PICS_NOTICE`
- [x] Separate talent-pool consent capture — `ConsentService`, `ConsentType.APPLICATION`/`TALENT_POOL` tracked independently
- [ ] Retention auto-delete/anonymize job — eligibility check built (`retention.py`), no recurring job
- [ ] Consent-withdrawal deletion workflow — eligibility check built, no job to act on it
- [x] Jurisdiction detection logic — only the default-to-strictest *rule*; detecting a real jurisdiction from candidate data is flagged, not built
- [x] Skill-ontology/synonym mapping table + maintenance interface — `SkillOntologyRepository`, zero import dependency on `scoring_engine` (see ASSUMPTIONS.md)
- [x] Explainability-on-request response generator — reads an existing `Score` only, never re-scores
- [x] Access/correction request handling workflow — request lifecycle only; no real candidate-data store to fulfill against yet
- [x] Feedback-to-scoring gate — satisfied by absence: Module 7's Feedback store isn't built yet, so no code path can exist; revisit once it is

## 7. Module 5 — Presentation Layer

A first slice is built: `presentation/app.py` (`hr-digital-employee-dashboard` console script,
optional `ui` extra) is a read-only Streamlit dashboard showing a comparison table across every
candidate scored from a resumes folder + JRP, and a drill-down per candidate (full score
breakdown, factual summary, interview questions, red flags) — built on the same Modules 1+2+3
pipeline as `cli.py`'s report, now factored into a shared `pipeline.py` so the intake/scoring
wiring exists in one place rather than duplicated across entry points. `cli.py`'s
`hr-digital-employee` console script remains the plain-text alternative. `jrp_editor/`
(`hr-digital-employee-jrp-editor` console script) still covers JRP configuration as a separate
tool, not yet merged into this dashboard. See ASSUMPTIONS.md for exactly what this slice does and
doesn't cover (no filtering, no pipeline-overview stats, no Pass/Reject action, no persistent
candidate store — every run is a fresh in-memory pipeline execution over the folder/JRP given).

- [ ] Notification cards (Email, Teams)
- [x] Comparison table
- [ ] Dashboard overview
- [ ] Dashboard filtering
- [x] Candidate drill-down
- [ ] Skill-gap visualizations
- [ ] JRP configuration UI
- [ ] Fairness-flag review UI
- [ ] Pass/Reject action + mandatory reason
- [ ] Decision logging
- [x] No-auto-filter UX review — trivially true (no filtering exists yet in this slice); revisit
      when filtering is built

## 8. Module 6 — Scheduling Coordination

- [ ] Microsoft Graph integration
- [ ] Google Calendar integration (if confirmed)
- [ ] Unified Free/Busy layer
- [ ] Time-zone handling
- [ ] Slot discovery
- [ ] Internal consensus poll
- [ ] Vote-timeout handling
- [ ] Retry/widen state machine
- [ ] Candidate confirmation + reschedule
- [ ] Candidate-side timeout
- [ ] Slot soft-locking
- [ ] Human escalation trigger
- [ ] Idempotent transactional booking
- [ ] Manus agent integration (scoped)
- [ ] Agent-action audit logging

## 9. Module 7 — Governance & Audit

- [x] Audit Log data model — `AuditEvent` + `AuditLog` protocol, `InMemoryAuditLog` stub, and a
      `SqliteAuditLog` implementation that survives a process restart (temporary/local-only; the
      real deployment data store is still an open decision, see ASSUMPTIONS.md)
- [ ] Audit event emission from all modules — Module 1's gateway now emits an audit event for
      every manual-review routing branch (unparseable, injection, low-confidence, ambiguous
      identity) plus successful processing, not just the injection case; Modules 2–6 not built yet
- [ ] Manual-review queue SLA monitoring
- [ ] Named owner assigned + wired
- [ ] Talent Pool tagging store
- [ ] Candidate feedback storage (predefined competency dimensions + remark)
- [ ] Feedback isolation enforcement (no code path to Scoring Engine)
- [ ] Retention auto-delete/anonymize job
- [ ] Consent-withdrawal deletion workflow
- [ ] Layered retention (identifiable vs. pseudonymized)
- [ ] Discrimination-appeal retention window
- [ ] Incident routing
- [ ] Human-assisted-mode fallback trigger
- [ ] Weekly operational review report

---

## 10. Pre-Go-Live Gates (from requirement.md §8 / SOP §6.1)

- [ ] 4-week manual-process baseline measured (entry time/resume, scheduling lead time)
- [ ] Parser validated against 200 annotated resumes, ≥95% accuracy
- [ ] Pre-deployment fairness back-test passed for every initial JRP
- [ ] Named operational owner in place
- [ ] Legal/Compliance sign-off on PDPO/GDPR/PIPL handling
- [ ] Rollback-to-human-assisted-mode path tested end-to-end
