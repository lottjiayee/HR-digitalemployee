# HR Digital Employee — Development Progress

**Last updated:** 2026-07-22
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
| 5 | Presentation Layer | Not Started | — | [module-5-presentation-layer.md](./modules/module-5-presentation-layer.md) |
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

222 tests, mypy --strict / ruff / ruff format all pass (OCR tests skip gracefully on a machine
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
- [x] Confidence scoring per field
- [x] Identity matching & dedup — heuristic name-similarity, not a real fuzzy-match library
- [x] Parser version stamping
- [ ] 200-resume accuracy validation (≥95%) — not started, needs a real annotated dataset

## 4. Module 2 — Scoring Engine

- [x] JRP data model — weights, must-have flags, curves; versioned via `JRPRepository`
- [x] Weight template presets (5 role types, exact percentages) + validation (sum to 100%)
- [x] Must-have gating check — separate `must_have_criteria` list, no weighted score computed on failure
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

None of this module itself is built yet. `cli.py`'s `hr-digital-employee` console script is a
temporary, separate command-line bridge over Modules 1+2 (a ranked-report printout, no dashboard,
no Pass/Reject action) — useful for running the pipeline at all right now, but not a substitute for
any item below. `jrp_editor/` (`hr-digital-employee-jrp-editor` console script, optional `ui` extra)
adds a one-page Streamlit form over the same YAML JRP config so HR can fill in weights/must-haves
through a form instead of hand-editing YAML — still not the real "JRP configuration UI" item below
(no auth, no history, not embedded in a dashboard). See ASSUMPTIONS.md.

- [ ] Notification cards (Email, Teams)
- [ ] Comparison table
- [ ] Dashboard overview
- [ ] Dashboard filtering
- [ ] Candidate drill-down
- [ ] Skill-gap visualizations
- [ ] JRP configuration UI
- [ ] Fairness-flag review UI
- [ ] Pass/Reject action + mandatory reason
- [ ] Decision logging
- [ ] No-auto-filter UX review

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
