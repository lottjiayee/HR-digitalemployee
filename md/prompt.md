# Vibe-Coding Prompt — HR Digital Employee

**Purpose of this file:** paste/feed this entire document to an autonomous coding agent as its
kickoff prompt. It is written to be executed with **no human in the loop** during the build. Every
decision that would normally require asking a person has already been resolved into a concrete
rule below (stub-and-document, per the project owner's instruction) so the agent never needs to
stop and wait for an answer.

**Inputs this prompt assumes are present in `md/`:** `requirement.md`, `design.md`,
`modules/module-1-intake-extraction.md` through `module-7-governance-audit.md`, `progress.md`,
`test.md`. Do not begin coding before reading all of them in full.

---

## 0. How to Use This Prompt

You are being given a complete, human-authored specification (the `md/` files) and asked to
produce a working, tested Python codebase from it with no further human input. Read this prompt
once fully before acting. Then read every file in `md/` fully before writing a single line of code.
Do not skim — the specification contains specific numeric thresholds (85% confidence, 95% parser
accuracy, four-fifths rule, 72h/48h timeouts, 3-round retry limits, 24-month retention) that must be
implemented exactly as stated, not approximated.

---

## 1. Mission

Build the HR Digital Employee system described in `md/requirement.md` and `md/design.md`: a resume
screening/scoring pipeline (Workflow A) and an interview scheduling coordinator (Workflow B), with
the governance, fairness, and human-in-the-loop controls specified throughout. Language: **Python**
(implied by the mandatory mypy/ruff/pytest gate — treat this as decided, not open).

## 2. Non-Negotiable Constraints

These are correctness properties, not style preferences. A build that fails any of these is not
"done" regardless of what the test suite says, so also write explicit tests that assert each one:

1. **Deterministic/LLM separation** (requirement.md FR-9, design.md §1): the scoring package must
   have **zero import dependency** on the AI-content package. Write an architectural test
   (e.g., inspect `import` statements, or use `import-linter`/a simple AST check) that fails the
   build if `scoring_engine` ever imports from `ai_content`, and vice versa for any function in
   `ai_content` that would write a score/tier field. There is no scenario in which this test is
   allowed to be skipped or weakened.
2. **Human-in-the-loop is structural, not procedural** (FR-13, FR-14): only the `presentation`
   package may write a `Decision` (Pass/Reject) record. Every other package must be structurally
   incapable of changing an application's status. Write a test that asserts no other module holds
   a reference to the Decision-writing function/method.
3. **No silent failure or silent disqualification** (FR-3, FR-4): any code path that cannot
   confidently produce a result must route to a manual-review state, never to a default "fail,"
   "reject," or "skip" outcome.
4. **Untrusted input by default** (NFR-3): resume content must pass through the injection/malware
   screening step before it reaches extraction or any LLM call — enforce this as a function
   signature / pipeline ordering constraint, not a convention.
5. **Audit everything decision-relevant**: every module that produces a decision-relevant output
   (score, JRP change, Pass/Reject, fairness flag, agent action) must emit an audit event
   (actor, timestamp, action, reason, version) through the shared `governance_audit` package's
   logging interface — never write ad hoc logs for these events.

## 3. Autonomy Rules — How to Handle Every Open Decision

The project owner explicitly resolved this in advance: **you are not permitted to pause, ask a
question, or leave a gap.** `md/progress.md` §2 splits open items into two lists — **§2a
(stubbable)** and **§2b (not stubbable)**. This prompt's rule always wins if the two files ever
seem to disagree: §2a items never block the build (stub them, per below); §2b items (named
operational owner, JRP ownership, Legal review, rollout sequencing, vendor/build path) are
real-world facts, not code — the build proceeds without them, they only gate go-live, and no
code-level workaround is needed or possible for them. Anything in §2a — cloud platform, second LLM
provider, data residency, Manus API specifics, WhatsApp/ATS integration, etc. — follow this rule:

> **Stub-and-document.** Build the real interface/abstraction the design calls for (e.g., a
> `CalendarProvider` protocol, an `LLMProvider` protocol, a `StoragePort` protocol). Implement it
> with a working **in-memory or local-filesystem stub** that is fully functional for tests and local
> runs (no real network calls to an undecided external vendor). Then write one entry per decision to
> `ASSUMPTIONS.md` at the repo root, in this format:
>
> ```
> ## <Decision name>
> **Status:** Stubbed — pending human decision (see md/progress.md §2)
> **What was built:** <interface name + stub implementation>
> **What a real implementation must satisfy:** <the interface's contract>
> **Why this default:** <one line — e.g., "keeps the module buildable and testable without
> committing to an unconfirmed vendor">
> ```

This applies to, at minimum: cloud platform / hosting, the second LLM provider (design.md §3.5),
Manus's exact API/SDK integration shape (stub it as an `agent execute_step()` protocol the
Scheduling Coordinator calls), Google Calendar vs. Microsoft-Graph-only, WhatsApp channel adapter,
ATS/HRIS integration, and data-residency-specific storage configuration.

**Never** silently pick a real paid vendor and wire up actual credentials or network calls for
anything on this list — that would be making the business decision for the owner, which they have
reserved for themselves. A stub is the correct output every time, no exceptions.

## 4. Roles: Supervisor Agent and Subagents

Adopt a two-tier structure for the build itself:

### Supervisor Agent (you, at the top level)
- Reads all of `md/` first; produces an internal build plan mirroring the 7 modules and their
  dependency order (each `module-N-*.md` §5 "Dependencies" section defines this graph).
- Scaffolds the repository (see §5) before any module-specific code is written.
- Delegates each module to one subagent, one module = one subagent, with a prompt built from:
  that module's `module-N-*.md` file in full, the relevant FR/NFR entries quoted out of
  `requirement.md`, the relevant `design.md` sections, and that module's section of `test.md`.
- Does **not** let a subagent start on a module whose dependencies (per §5 of its module.md) are
  not yet complete and gate-passing — except modules with no unmet dependency, which may run
  concurrently.
- After each subagent reports back, the Supervisor: runs the full quality gate (§6) against the
  **whole accumulated repo**, not just the new module, to catch cross-module regressions; updates
  `md/progress.md` checkboxes for that module; only then dispatches the next wave of subagents.
- After all 7 modules pass individually, runs the end-to-end scenarios in `test.md` §8 as
  integration tests across the assembled codebase.
- Writes a final summary to `BUILD_REPORT.md`: what was built, current progress.md state, and the
  full list of items now waiting in `ASSUMPTIONS.md` for a human decision.

### Subagent (one per module)
- Scope strictly to its assigned module — do not modify another module's package except to add a
  new, clearly-named integration point (e.g., a protocol interface another module will implement
  against) and flag that change explicitly to the Supervisor.
- Implements the module's code, the module's stub adapters per §3, and pytest tests covering
  **every test ID** listed for that module in `test.md` (convert each "Steps → Expected Result" row
  into one or more real pytest test functions with the same ID as a test name/marker, e.g.
  `def test_t1_4_low_confidence_must_have_routes_to_manual_review():`).
- Does not mark any checklist item in its module.md/progress.md section as done until the
  corresponding code exists **and** the corresponding test(s) pass.
- Runs the quality gate (§6) locally before reporting completion; a subagent report that hasn't run
  these gates is not a valid completion signal.

## 5. Repository Structure

```
pyproject.toml                # mypy, ruff, pytest config (see §6)
ASSUMPTIONS.md                # per §3
BUILD_REPORT.md               # written by Supervisor at the end
src/
  hr_digital_employee/
    intake_extraction/        # Module 1
    scoring_engine/           # Module 2
    ai_content/                # Module 3
    fairness_compliance/       # Module 4
    presentation/               # Module 5
    scheduling_coordination/    # Module 6
    governance_audit/           # Module 7
tests/
  intake_extraction/
  scoring_engine/
  ai_content/
  fairness_compliance/
  presentation/
  scheduling_coordination/
  governance_audit/
  integration/                # test.md §8 end-to-end scenarios
```

Each module package exposes its cross-module interface (the "Downstream" contracts named in its
module.md §5) as explicit typed protocols/dataclasses in an `interfaces.py` (or `__init__.py`)
so other modules depend only on that surface, never on internal implementation details.

## 6. Quality Gates — Mandatory, No Exceptions

Every module, and the repo as a whole after each integration step, must pass all three:

- **mypy**: run in strict mode. Suggested `pyproject.toml` baseline:
  ```toml
  [tool.mypy]
  strict = true
  warn_unused_ignores = true
  disallow_any_generics = true
  ```
  Zero errors. Do not suppress with blanket `# type: ignore` — a genuinely unavoidable ignore must
  target a specific error code and include a one-line reason comment.
- **ruff**: run both `ruff check .` and `ruff format --check .`. Zero violations. Use ruff's
  recommended default rule set plus `I` (import sorting) and `UP` (pyupgrade) at minimum.
- **pytest**: `pytest --cov=src --cov-report=term-missing`. All tests pass. Target ≥85% coverage
  per module; if a specific line is untestable without a real external dependency (per a §3 stub),
  that's expected — the stub itself must still be fully covered.

A module is not complete if any of these three fail. Fix the code, not the gate.

## 7. Build Process (the loop the Supervisor follows)

1. Read all of `md/` in full.
2. Scaffold the repo per §5; commit an empty-but-passing gate baseline (empty packages, `pyproject.toml`
   configured, gates green on a trivial hello-world test) before any module work starts.
3. Determine dependency order from each module's §5 (verified against every module.md's actual
   "Dependencies" section — do not re-derive this from scratch, use this table as authoritative):
   - Wave 1 (no unmet deps): Module 1 (Intake & Extraction), Module 7 (Governance & Audit — other
     modules depend on its logging interface existing, so build its interface early even though its
     own full feature set can develop in parallel).
   - Wave 2: Module 2 (Scoring Engine — depends on Module 1 only).
   - Wave 3: Module 3 (AI Content — depends on Module 1 + Module 2's read interface) and Module 4
     (Fairness — depends on Module 2's score/tier outcomes). These two may run concurrently: neither
     depends on the other, both only depend on Module 2, which is already complete by this wave.
   - Wave 4: Module 5 (Presentation — depends on Modules 2, 3, and 4 all being complete).
   - Wave 5: Module 6 (Scheduling Coordination — depends on Module 5's shortlist/Pass action).
4. For each wave, dispatch one subagent per module in that wave concurrently.
5. On each subagent completion: run full quality gates on the whole repo; update `md/progress.md`;
   only advance to the next wave once every module in the current wave is gate-passing.
6. After Wave 5: run `test.md` §8 end-to-end scenarios as `tests/integration/`.
7. Write `BUILD_REPORT.md` and stop. Do not attempt to resolve anything in `ASSUMPTIONS.md` —
   those are explicitly reserved for the human owner.

## 8. Module → Subagent Assignment

| Wave | Module | Subagent input |
|---|---|---|
| 1 | Module 1 — Intake & Extraction | `module-1-intake-extraction.md`, requirement.md FR-1–5/NFR-1/NFR-3, design.md §3.1–3.3, test.md §1 |
| 1 | Module 7 — Governance & Audit (interface first) | `module-7-governance-audit.md`, requirement.md NFR-2/4/5/FR-24/28/29, design.md §3.11–3.12, test.md §7 |
| 2 | Module 2 — Scoring Engine | `module-2-scoring-engine.md`, requirement.md FR-6–9/27/31/NFR-5/6, design.md §3.4, test.md §2 |
| 3 | Module 3 — AI-Assisted Content | `module-3-ai-content-generation.md`, requirement.md FR-10/12, design.md §3.5/§1.1, test.md §3 |
| 3 | Module 4 — Fairness & Compliance | `module-4-fairness-compliance.md`, requirement.md FR-20–23/25–27/30, design.md §3.6, test.md §4 |
| 4 | Module 5 — Presentation Layer | `module-5-presentation-layer.md`, requirement.md FR-11/13/14, design.md §3.7–3.8, test.md §5 |
| 5 | Module 6 — Scheduling Coordination | `module-6-scheduling-coordination.md`, requirement.md FR-15–19, design.md §3.9–3.10/§1.1, test.md §6 |

## 9. Critical Architectural Invariants to Verify Before Reporting Done

Beyond passing tests, explicitly verify and record the result of each:

- [ ] No import edge from `ai_content` → `scoring_engine` internals (or vice versa beyond the
      read-only structured-output interface)
- [ ] Only `presentation` package writes `Decision` records
- [ ] `scheduling_coordination`'s Manus stub only exposes the Calendar Adapter + Notification
      Service tool surface — no direct calendar-provider credentials in the agent-facing interface
- [ ] Every module that produces a decision-relevant output calls into `governance_audit`'s logging
      interface — grep for any bespoke `print`/`logging` calls used in place of it and replace them
- [ ] All confidence/threshold/timeout/retry numbers match the spec exactly (85%, 95%, four-fifths
      = 0.8, 72h + 48h, 3 rounds / 7 days, 24 months / 30 days, tier defaults 80%/60%, all 5 JRP
      weight-template percentages) — these must be named constants, not magic numbers, and must
      match `requirement.md`/`design.md` verbatim
- [ ] No code path exists from `governance_audit`'s stored `Feedback` records into `scoring_engine`
      — feedback is profile-context-only (FR-28) unless a future change has explicitly passed
      `fairness_compliance`'s gate (FR-30); verify by the same import/reference check as invariant 1

## 10. Definition of Done

- **Per module**: every checklist item in that module's `md/modules/module-N-*.md` §7 is checked
  off, every test ID in that module's `test.md` section is implemented and passing, and mypy/ruff/
  pytest are clean for that module's code.
- **Overall**: all 7 modules done per the above, `test.md` §8 integration scenarios pass, §9's
  invariants are verified, `ASSUMPTIONS.md` lists every stubbed decision, `md/progress.md` reflects
  true current state, and `BUILD_REPORT.md` exists summarizing the run.

## 11. Reporting

Update `md/progress.md` checkboxes as real progress is made — not in a final batch at the end. If
a subagent discovers a checklist item in a module.md that the code doesn't actually need (or
discovers a missing one), update that module.md file directly and note the change in
`BUILD_REPORT.md`; do not silently diverge from the tracked plan.

---

## 12. Execution Notes (adapt to whichever agent runtime is actually running this prompt)

This prompt is written to be runtime-agnostic — "Supervisor" and "Subagent" are roles, not a
specific tool's API. Two common ways to execute it:

- **If run in Claude Code**: use the Agent tool once per subagent (per §4/§8), running independent
  modules within a wave in parallel tool calls; use TodoWrite to track the wave/module loop in
  addition to the `md/progress.md` file itself, which remains the durable, human-readable record.
- **If run in another autonomous coding framework**: map "Supervisor" to whatever top-level
  orchestrating context your framework provides, and "Subagent" to its sub-task/sub-session
  primitive. The gate requirements (§6), invariants (§9), and stub-and-document rule (§3) are
  framework-independent and must be preserved regardless of runtime.

Do not begin without having read every file in `md/` in full. Begin now.
