# Module 2: Scoring Engine

**Status:** Not Started
**Design source:** [design.md](../design.md) §3.4
**Requirement source:** [requirement.md](../requirement.md) FR-6–FR-9, NFR-5, NFR-6

---

## 1. Purpose

Deterministically score a candidate against a role's Job Requirement Profile (JRP). This is the
component the SOP's objectivity claims rest on — it must be provably free of LLM/agent influence.

## 2. Components Covered

| Component | Design ref | Responsibility |
|---|---|---|
| Scoring Engine | §3.4 | Must-have gating, weighted dimension scoring, tier classification |

## 3. Requirements Covered

- **FR-6**: JRP definition per role — weight template selection + fine-tuning (weights sum to 100%)
- **FR-7**: Must-have vs. weighted criteria tagging
- **FR-8**: Configurable matching curve per dimension (Linear/Step/Buffered)
- **FR-9**: Scoring is deterministic; LLM-assisted output never alters score/tier/gating
- **NFR-5**: Every score stamped with scoring-engine version; one hiring round = one version
- **NFR-6**: Automatic rollback to human-assisted mode if accuracy/metrics degrade

## 4. Key Design Constraints

- Scoring sequence is fixed: must-have check → disqualify if failed → weighted dimension scoring
  (curve-adjusted) → weight multiplication → normalize to 0–100 → tier assignment.
- Consumes **only structured extraction output** from Module 1 — never raw resume text, never
  LLM-generated content, as inputs to the calculation.
- Weight templates (General 40/30/15/15, Senior technical, Junior/graduate, Managerial,
  Licensed/compliance) are configuration, not hardcoded per role.
- Every JRP weight/threshold/must-have change is audit-logged (actor, timestamp, reason) — feeds
  Module 7.
- Trainable skills should not be must-have; Educational Level weight defaults to ≤15% (JRP
  configuration guidance, not a hard system constraint, but should be enforced as a default/warning).

## 5. Dependencies

- **Upstream:** Module 1 (structured extraction output)
- **Downstream:** Module 3 (LLM content generation consumes scoring context for question
  suggestions), Module 4 (Fairness testing reads score/tier outcomes), Module 5 (Presentation
  displays scores), Module 7 (version stamping, audit)

## 6. Open Questions

- None specific to this module beyond the general tech-stack/platform questions in design.md §10.

## 7. Progress Checklist

- [ ] JRP data model (weights, must-have flags, curves, versioning)
- [ ] Weight template presets (5 role types) + validation (sum to 100%)
- [ ] Must-have gating check (disqualify path, no weighted calc on fail)
- [ ] Matching curve implementations: Linear, Step, Buffered
- [ ] Weighted score calculation + normalization to 0–100
- [ ] Tier classification (High/Mid/Low Match thresholds configurable)
- [ ] JRP change audit logging (who/when/why)
- [ ] Scoring-engine version stamping on every Score record
- [ ] One-round-one-version enforcement (block mixed-version scoring within a hiring round)
- [ ] Rollback trigger hook (flips to human-assisted mode on metric breach)

## 8. Testing

See [test.md](../test.md) §2 for module-specific test steps.
