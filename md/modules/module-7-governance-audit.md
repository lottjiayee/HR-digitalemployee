# Module 7: Governance & Audit

**Status:** Not Started
**Design source:** [design.md](../design.md) §3.11–3.12
**Requirement source:** [requirement.md](../requirement.md) NFR-2, NFR-4, NFR-5 (cross-cutting)

---

## 1. Purpose

Provide the shared, cross-cutting record-keeping and long-term storage every other module writes
to — the mechanism that makes "traceable" and "auditable" true system properties rather than
policy statements.

## 2. Components Covered

| Component | Design ref | Responsibility |
|---|---|---|
| Talent Pool Store | §3.11 | Long-term tagged candidate records for future search; retention/anonymization enforcement; also holds post-interview `Feedback` records |
| Audit & Versioning Log | §3.12 | Append-only log of every decision-relevant action across all modules |

## 3. Requirements Covered (cross-cutting, referenced by other modules)

- **NFR-2**: Manual-review queue SLA (1 business day) — monitoring and breach alerting
- **NFR-4**: Least-privilege access — credential scoping and usage logging across modules
- **NFR-5**: Version stamping on every score; one hiring round = one engine/parser version
- **FR-24**: Automatic talent-pool tagging from extracted skills/experience/education/industry
- **FR-28**: Post-interview feedback stored solely as profile context — no write path to scoring
- **FR-29**: Feedback captured against predefined competency dimensions; free text as remark only
- Also underlies FR-14 (decision logging), FR-20 (fairness audit trail), FR-23 (retention), FR-30
  (feedback-to-scoring gate — this module stores the feedback, Module 4 owns the gate itself)

## 4. Key Design Constraints

- Audit Log is **append-only**: every entry records (actor, timestamp, action, reason, version).
- Layered retention (SOP 4.3): identifiable resume/contact data is erasable on request; pseudonymized
  Pass/Reject decision logs are retained separately for a defined discrimination-appeal window, then
  deleted. An erasure request removes the identifiable layer only.
- Talent Pool retention: 24-month default auto-delete/anonymize for non-hired candidates; 30-day
  deletion on consent withdrawal (coordinates with Module 4's consent tracking).
- Manual-review queue depth is monitored; an SLA breach (>1 business day) alerts the named
  operational owner (requirement.md §7.4 — owner still to be named).
- Named-owner routing: every queue, alert, and escalation across all modules routes to a specific
  person, not a shared mailbox.
- Feedback records (FR-28–FR-29) are entered against predefined, role-linked competency dimensions
  (e.g., communication 1–5); free text is accepted only as a supplementary remark — undefined
  labels (e.g., "cultural fit") are rejected as structured fields, not silently accepted.
- Feedback has **no consumer other than a human reader** viewing a candidate's profile, unless
  Module 4's FR-30 gate has explicitly approved a scoring-relevant use — this store does not push
  data to Module 2 under any automatic condition.
- Weekly operational review: queue volumes, injection flags (Module 1), scheduling escalations
  (Module 6), incident follow-ups — reviewed by the named owner, feeding the quarterly baseline
  re-measurement.
- Incident routing: channel outages, expired calendar auth, parser errors alert IT + the HR owner;
  system falls back to human-assisted mode during outages.

## 5. Dependencies

- **Upstream:** every other module writes audit events here (Modules 1–6)
- **Downstream:** none — this is the terminal record-keeping layer, read by compliance/legal
  reporting and candidate-appeal processes

## 6. Open Questions

- **Named operational owner** (requirement.md §7.4) — who is accountable for queues/alerts/escalations?
- **Data residency** (design.md §10.5) — affects where the Audit Log and Talent Pool physically live.
- **Discrimination-appeal retention window length** for pseudonymized decision logs — not specified
  in the SOP as a concrete duration; needs a number before this can be built.

## 7. Progress Checklist

- [ ] Append-only Audit Log data model (actor, timestamp, action, reason, version)
- [ ] Audit event emission wired from every other module (1–6) — Module 1 complete (all
      manual-review routing reasons plus successful processing); Modules 2–6 not built yet
- [ ] Manual-review queue depth monitoring + SLA breach alerting
- [ ] Named operational owner assigned and wired into alert routing
- [ ] Talent Pool tagging store (skills/experience/education/industry tags, FR-24)
- [ ] Candidate feedback storage (predefined competency dimensions + remark, FR-28–FR-29)
- [ ] Feedback isolation enforcement (no code path from Feedback store to Scoring Engine)
- [ ] 24-month retention auto-delete/anonymize scheduled job
- [ ] 30-day consent-withdrawal deletion workflow
- [ ] Layered retention: identifiable-data erasure vs. pseudonymized decision-log retention
- [ ] Discrimination-appeal retention window defined and enforced
- [ ] Incident routing (channel outage, calendar auth expiry, parser errors → IT + owner)
- [ ] Human-assisted-mode fallback trigger during outages
- [ ] Weekly operational review report (queue volumes, injection flags, escalations, incidents)

## 8. Testing

See [test.md](../test.md) §7 for module-specific test steps.
