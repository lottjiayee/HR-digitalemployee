# Module 4: Fairness & Compliance

**Status:** In Progress — adverse-impact testing + core services built, rough draft (see md/progress.md)
**Design source:** [design.md](../design.md) §3.6
**Requirement source:** [requirement.md](../requirement.md) FR-20–FR-23

---

## 1. Purpose

Measure and surface adverse impact in scoring outcomes, and enforce PDPO-driven consent/retention
rules — the mechanism that makes the system's "objectivity" and "compliance" claims evidenced
rather than asserted.

## 2. Components Covered

| Component | Design ref | Responsibility |
|---|---|---|
| Fairness & Adverse-Impact Service | §3.6 | Four-fifths rule testing, statistical corroboration, flagging |

*(Consent/retention enforcement spans this module and Module 7's Talent Pool retention job — see
Module 7 for the scheduled deletion/anonymization mechanics.)*

## 3. Requirements Covered

- **FR-20**: Four-fifths adverse-impact testing per JRP, pre-deployment, ≥quarterly thereafter,
  **and whenever that JRP's weights or must-have rules change**
- **FR-21**: Demographic data voluntary, self-declared, stored separately, never a scoring input
- **FR-22**: Collection notice (PICS) at intake; talent-pool consent separate/unbundled
- **FR-23**: Non-hired candidate data auto-deletes/anonymizes at 24 months; withdrawal → deletion
  within 30 days
- **FR-25**: Explainability on request — human-readable evaluation explanation derived from the
  Matching Analysis (Module 5's Candidate Summary Report)
- **FR-26**: Candidate access-to and correction-of their held personal data (PDPO right)
- **FR-27**: Own and maintain the skill-ontology/synonym mapping table that Module 2's Scoring
  Engine reads during keyword matching (phrasing/language-bias mitigation)
- **FR-30**: Gate for any future proposal to use post-interview feedback (Module 7) as a scoring
  input — must pass this module's adverse-impact testing before deployment

## 4. Key Design Constraints

- Selection rate = proportion of a group reaching High/Mid tier or passed by HR. Four-fifths rule
  flags if any group's rate < 80% of the highest group's rate.
- Four-fifths is a **trigger, not a verdict** — corroborate with a significance test (chi-square or
  standardized difference) where sample size allows before concluding anything.
- Protected characteristics tested (Hong Kong): sex/marital/pregnancy (Cap. 480), family status
  (Cap. 527), disability (Cap. 487), race (Cap. 602).
- This service has **no write path** back into the Scoring Engine (Module 2) or candidate records —
  flags go to HR/JRP owners for manual review only.
- Demographic data collection is voluntary and stored separately from the scoring pipeline;
  fairness metrics are aggregate-only, never reconstructing an individual's protected attributes.
- Disparate-treatment check: JRP definitions reviewed to confirm no protected characteristic (or
  transparent proxy) is used directly as a scoring input.
- Jurisdictional layering: PDPO baseline, GDPR Article 22 rights for EU candidates, PIPL for
  Mainland China candidates, default to strictest framework when jurisdiction is undetermined.
- Skill-ontology mapping (FR-27) is maintained here and read-only from Module 2 — this module owns
  updates to the ontology; Module 2 never writes to it.
- Explainability responses (FR-25) are generated from existing Matching Analysis data — this
  module must not perform new scoring or re-derive a result, only explain the one already produced
  by Module 2.
- The feedback-loop gate (FR-30) is a one-way door: until a feedback-informed scoring change has
  passed this module's adverse-impact testing and been logged, Module 7's stored feedback records
  remain read-only context with no consumer other than a human reader.

## 5. Dependencies

- **Upstream:** Module 2 (score/tier outcomes to test), Module 1 (candidate records)
- **Downstream:** Module 7 (fairness flags and JRP-change rationale feed the audit trail)

## 6. Open Questions

- None specific beyond the general data-residency question in design.md §10.5, which affects where
  demographic data can be stored.

## 7. Progress Checklist

- [ ] Voluntary demographic self-declaration collection (separate from application data) —
      `DemographicRecord` modeled; no intake collection flow yet (Module 5's job)
- [x] Selection-rate calculation per protected-characteristic group, per JRP
- [x] Four-fifths rule check + flagging — `AdverseImpactTestingService` audit-logs every result
      (flagged or passing), per md/prompt.md §2 invariant 5
- [x] Statistical significance corroboration (chi-square / standardized difference) — two-proportion
      z-test picked over chi-square to avoid a scipy dependency (ASSUMPTIONS.md)
- [ ] Pre-deployment back-test against historical/sample data for new/changed JRPs — no
      "deployment"/activation concept exists yet to gate
- [ ] Quarterly re-test scheduler for live JRPs — needs Module 7's job infrastructure (not built)
- [ ] Re-test trigger on any JRP weight/must-have change (not calendar-only) — same gap as above
- [ ] Disparate-treatment review workflow (protected-characteristic/proxy check on JRP definitions)
- [x] PICS collection notice at intake (all channels)
- [x] Separate, unbundled talent-pool consent capture
- [ ] 24-month retention auto-delete/anonymize job (coordinates with Module 7) — eligibility check
      built (`retention.py`), no recurring job to act on it
- [ ] Consent-withdrawal → 30-day deletion workflow — eligibility check built, no job
- [x] Jurisdiction detection + default-strictest-framework logic (PDPO/GDPR/PIPL) — only the
      default-when-undetermined *rule*; real detection needs candidate-location data not available
      yet (flagged, not stubbed — see ASSUMPTIONS.md)
- [x] Skill-ontology/synonym mapping table + maintenance interface (consumed read-only by Module 2) —
      `SkillOntologyRepository`, zero import dependency on `scoring_engine` (structural typing;
      see ASSUMPTIONS.md)
- [x] Explainability-on-request response generator (reads existing Matching Analysis only)
- [x] Access/correction request handling workflow — request lifecycle only; no real candidate-data
      store to fulfill against yet
- [x] Feedback-to-scoring gate (blocks Module 7 feedback from reaching Module 2 without passing
      this checklist's adverse-impact re-test first) — satisfied by absence: Module 7's Feedback
      store isn't built yet, so no such code path can exist; revisit once it is

## 8. Testing

See [test.md](../test.md) §4 for module-specific test steps.
