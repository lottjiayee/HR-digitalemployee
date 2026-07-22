# HR Digital Employee — Development Progress

**Last updated:** 2026-07-21
**Source docs:** [requirement.md](./requirement.md), [design.md](./design.md), [modules/](./modules/)

Status values used throughout: `Not Started` → `In Progress` → `Blocked` → `Done`

---

## 1. Overall Module Status

| # | Module | Status | Open items (see §2 — stubbed in code, not blocking) | Module doc |
|---|---|---|---|---|
| 1 | Intake & Extraction | In Progress — core pipeline built, rough draft | Real channel integration and structured-field splitting still stubbed (PDF byte-to-text extraction is real via `pypdf`; image OCR is real via local Tesseract, cloud OCR not chosen); malware scan and 200-resume validation not started | [module-1-intake-extraction.md](./modules/module-1-intake-extraction.md) |
| 2 | Scoring Engine | In Progress — core scoring math + Module 1 adapter built, rough draft | Module 1 -> Module 2 profile adapter is a regex-heuristic stub (word-form numbers, open-ended date ranges not handled); skill ontology is an exact-match/synonym-map stub pending Module 4; one-round-one-version enforcement and NFR-6 rollback hook not started | [module-2-scoring-engine.md](./modules/module-2-scoring-engine.md) |
| 3 | AI-Assisted Content Generation | Not Started | 2nd LLM provider not chosen (stubbed) | [module-3-ai-content-generation.md](./modules/module-3-ai-content-generation.md) |
| 4 | Fairness & Compliance | Not Started | — | [module-4-fairness-compliance.md](./modules/module-4-fairness-compliance.md) |
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

142 tests, mypy --strict / ruff / ruff format all pass (OCR tests skip gracefully on a machine
without the Tesseract binary). See `ASSUMPTIONS.md` at the repo root for every stub this draft
makes — including an observed, non-theoretical accuracy tradeoff for local OCR vs. a managed cloud
provider. Modules 3, 4, and 6 are empty placeholder packages only; Module 5 has this CLI as a
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

- [ ] LLM provider selected + integrated
- [ ] Structured-input-only enforcement
- [ ] Summary generation
- [ ] Sentence-level anchoring
- [ ] Interview question generation
- [ ] Red-flag detection
- [ ] Red-flag fairness framing review
- [ ] Model/prompt version stamping
- [ ] Hallucination-audit hook
- [ ] Hallucination threshold + suspension logic

## 6. Module 4 — Fairness & Compliance

- [ ] Voluntary demographic collection
- [ ] Selection-rate calculation
- [ ] Four-fifths rule check
- [ ] Statistical significance corroboration
- [ ] Pre-deployment back-test
- [ ] Quarterly re-test scheduler
- [ ] Re-test trigger on JRP weight/must-have change (not calendar-only)
- [ ] Disparate-treatment review workflow
- [ ] PICS collection notice
- [ ] Separate talent-pool consent capture
- [ ] Retention auto-delete/anonymize job
- [ ] Consent-withdrawal deletion workflow
- [ ] Jurisdiction detection logic
- [ ] Skill-ontology/synonym mapping table + maintenance interface
- [ ] Explainability-on-request response generator
- [ ] Access/correction request handling workflow
- [ ] Feedback-to-scoring gate (blocks Module 7 feedback reaching Module 2 without re-test)

## 7. Module 5 — Presentation Layer

None of this module itself is built yet. `cli.py`'s `hr-digital-employee` console script is a
temporary, separate command-line bridge over Modules 1+2 (a ranked-report printout, no dashboard,
no Pass/Reject action) — useful for running the pipeline at all right now, but not a substitute for
any item below. See ASSUMPTIONS.md.

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
