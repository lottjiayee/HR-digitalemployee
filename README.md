# HR Digital Employee

Automated resume screening/scoring and interview-scheduling coordination for an HR department,
built from an internal SOP with heavy emphasis on human-in-the-loop control, fairness testing, and
Hong Kong PDPO compliance.

**Status:** Planning/specification phase — no code has been written yet. A full audit of the
documents below found several gaps (dropped SOP content, a couple of internal contradictions in
`prompt.md`) that should be fixed before the autonomous build in `prompt.md` is actually run. See
`md/progress.md` for the live tracking checklist.

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
with no human in the loop, using a Supervisor/Subagent pattern (one subagent per module) and
mandatory mypy/ruff/pytest quality gates. It has **not been executed yet** — recommended first step
is a dry run of Wave 1 (Modules 1 and 7) rather than a full unattended run, and the known issues
from the latest audit should be fixed first (see Status above).

---

**Last updated:** 2026-07-16
