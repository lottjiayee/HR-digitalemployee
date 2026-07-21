# HR Digital Employee

Automated resume screening/scoring and interview-scheduling coordination for an HR department,
built from an internal SOP with heavy emphasis on human-in-the-loop control, fairness testing, and
Hong Kong PDPO compliance.

**Status:** Rough first-draft code now exists (`src/hr_digital_employee/`, Python) covering Module 1
(Intake & Extraction) end-to-end — including real PDF text extraction via `pypdf` and local image
OCR via Tesseract, not just plain-text stand-ins — and Module 7's audit-log interface — 54 tests,
mypy --strict / ruff all passing. Modules 2–6 are still empty placeholders. See `ASSUMPTIONS.md` at
the repo root for every
stub this draft makes, and `md/progress.md` for the live tracking checklist and current open
decisions.

New to this project? Start with [GLOSSARY.md](GLOSSARY.md) — it explains the domain terms (JRP,
four-fifths rule, tiers, etc.) and project-specific ones (Manus, stub-and-document, modules, waves)
used throughout the docs below.

---

## Document Map (read in this order)

| Order | File | What it's for |
|---|---|---|
| 1 | [md/requirement.md](md/requirement.md) | What the system must do and why — for stakeholder/leadership sign-off |
| 2 | [md/design.md](md/design.md) | System architecture: components, data model, integrations, security |
| 3 | [md/modules/](md/modules/) | One file per module (7 total) — scope, requirements covered, dependencies, checklist |
| 4 | [md/progress.md](md/progress.md) | Live status tracker across all modules, plus the master list of decisions still open |
| 5 | [md/test.md](md/test.md) | Acceptance-criteria test steps per module, mapped to requirement.md's FR/NFR numbers |
| 6 | [md/prompt.md](md/prompt.md) | Kickoff prompt for an autonomous coding agent to build the system from the above — **not yet run** |

## Modules

1. Intake & Extraction
2. Scoring Engine
3. AI-Assisted Content Generation
4. Fairness & Compliance
5. Presentation Layer
6. Scheduling Coordination
7. Governance & Audit

Each has its own file in [md/modules/](md/modules/) with full detail.

## Open Decisions

A number of business/technical decisions are intentionally left open rather than guessed (cloud
platform, second LLM provider, data residency, named operational owner, and others). The current,
authoritative list lives in [md/progress.md](md/progress.md) §2 — check there rather than assuming
this README is up to date on it.

## Using prompt.md

`md/prompt.md` is written to be handed to an autonomous coding agent to build the entire system
with no human in the loop, using a Supervisor/Subagent pattern (one subagent per module, across 5
dependency-ordered waves) and mandatory mypy/ruff/pytest quality gates. It has **not been executed
yet** — recommended first step is a dry run of Wave 1 (Modules 1 and 7) rather than a full
unattended run.

---

**Last updated:** 2026-07-20 (fixed two bugs found by manually running real-world files through the
pipeline — non-PDF binaries no longer silently decode into garbage and sail through as
empty-but-accepted candidates; the experience-section heuristic now also recognizes "Work
History"/"Employment History" — and added local Tesseract OCR support for resumes submitted
directly as a JPEG/PNG/GIF/BMP/WEBP image, with an observed accuracy tradeoff against a managed
cloud OCR provider. See `ASSUMPTIONS.md` for detail.)
