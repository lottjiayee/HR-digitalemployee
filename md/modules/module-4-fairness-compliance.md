# Module 4: Fairness & Compliance

**Status:** Not Started
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

- **FR-20**: Four-fifths adverse-impact testing per JRP, pre-deployment and ≥quarterly thereafter
- **FR-21**: Demographic data voluntary, self-declared, stored separately, never a scoring input
- **FR-22**: Collection notice (PICS) at intake; talent-pool consent separate/unbundled
- **FR-23**: Non-hired candidate data auto-deletes/anonymizes at 24 months; withdrawal → deletion
  within 30 days

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

## 5. Dependencies

- **Upstream:** Module 2 (score/tier outcomes to test), Module 1 (candidate records)
- **Downstream:** Module 7 (fairness flags and JRP-change rationale feed the audit trail)

## 6. Open Questions

- None specific beyond the general data-residency question in design.md §10.5, which affects where
  demographic data can be stored.

## 7. Progress Checklist

- [ ] Voluntary demographic self-declaration collection (separate from application data)
- [ ] Selection-rate calculation per protected-characteristic group, per JRP
- [ ] Four-fifths rule check + flagging
- [ ] Statistical significance corroboration (chi-square / standardized difference)
- [ ] Pre-deployment back-test against historical/sample data for new/changed JRPs
- [ ] Quarterly re-test scheduler for live JRPs
- [ ] Disparate-treatment review workflow (protected-characteristic/proxy check on JRP definitions)
- [ ] PICS collection notice at intake (all channels)
- [ ] Separate, unbundled talent-pool consent capture
- [ ] 24-month retention auto-delete/anonymize job (coordinates with Module 7)
- [ ] Consent-withdrawal → 30-day deletion workflow
- [ ] Jurisdiction detection + default-strictest-framework logic (PDPO/GDPR/PIPL)

## 8. Testing

See [test.md](../test.md) §4 for module-specific test steps.
