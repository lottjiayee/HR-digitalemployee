# Module 2: Scoring Engine

**Status:** In Progress — core scoring math built, rough draft (see md/progress.md)
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
- **FR-27**: Skill-ontology/synonym mapping backs keyword matching (fairness mitigation, ontology
  owned/maintained by Module 4)
- **FR-31**: Tier classification defaults (High 80–100% / Mid 60–79% / Low <60%), configurable per JRP
- **NFR-5**: Every score stamped with scoring-engine version; one hiring round = one version
- **NFR-6**: Automatic rollback to human-assisted mode if accuracy/metrics degrade

### Weight Templates (default presets, per FR-6)

| Role type | Mandatory Skills | Experience Tenure | Educational Level | Project Relevance |
|---|---|---|---|---|
| General (default) | 40% | 30% | 15% | 15% |
| Senior technical | 35% | 35% | 10% | 20% |
| Junior / graduate | 45% | 5% | 30% | 20% |
| Managerial | 25% | 30% | 15% | 30% |
| Licensed / compliance | 50% | 20% | 20% | 10% |

HR can fine-tune any of these per JRP; the system validates the result still sums to 100%.

## 4. Key Design Constraints

- Scoring sequence is fixed: must-have check and weighted dimension scoring (curve-adjusted →
  weight multiplication → normalize to 0–100 → tier assignment) both run every time. A failed
  must-have never withholds the score — it is flagged alongside the fully-computed result so HR
  sees the whole profile before deciding (SOP 2.2.2/2.2.4, revised 2026-07-22).
- Consumes **only structured extraction output** from Module 1 — never raw resume text, never
  LLM-generated content, as inputs to the calculation.
- Weight templates (see table above) are configuration, not hardcoded per role — HR can override
  any preset per JRP as long as the total remains 100%.
- Tier thresholds (80%/60% defaults) are configuration per JRP, not hardcoded, but must ship with
  these defaults rather than an empty/undefined range.
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

- [x] JRP data model (weights, must-have flags, curves, versioning)
- [x] Weight template presets (5 role types, exact percentages above) + validation (sum to 100%)
- [x] Must-have gating check (flag-alongside-full-score path, per the 2026-07-22 SOP revision —
      does not withhold the weighted calc on fail)
- [x] Matching curve implementations: Linear, Step, Buffered
- [x] Skill-ontology-backed matching (consumption point built; real ontology is Module 4's, not
      built yet — see ASSUMPTIONS.md)
- [x] Weighted score calculation + normalization to 0–100
- [x] Tier classification with 80%/60% default thresholds (configurable per JRP)
- [x] JRP change audit logging (who/when/why)
- [x] Scoring-engine version stamping on every Score record (both `scoring_engine_version` and `parser_version`, per NFR-5) — plus an audit-logged (non-blocking) warning when a JRP's Educational Level weight exceeds the 15% guideline default
- [ ] One-round-one-version enforcement (block mixed-version scoring within a hiring round)
- [ ] Rollback trigger hook (flips to human-assisted mode on metric breach)
- [x] Module 1 -> Module 2 profile adapter (`ExtractedResume` -> `CandidateProfile`; regex-heuristic
      stub, same spirit as Module 1's own extraction heuristics — see ASSUMPTIONS.md)

## 8. Testing

See [test.md](../test.md) §2 for module-specific test steps.
