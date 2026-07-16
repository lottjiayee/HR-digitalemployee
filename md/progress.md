# HR Digital Employee — Development Progress

**Last updated:** (update this date whenever you edit this file)
**Source docs:** [requirement.md](./requirement.md), [design.md](./design.md), [modules/](./modules/)

Status values used throughout: `Not Started` → `In Progress` → `Blocked` → `Done`

---

## 1. Overall Module Status

| # | Module | Status | Blocked by | Module doc |
|---|---|---|---|---|
| 1 | Intake & Extraction | Not Started | — | [module-1-intake-extraction.md](./modules/module-1-intake-extraction.md) |
| 2 | Scoring Engine | Not Started | — | [module-2-scoring-engine.md](./modules/module-2-scoring-engine.md) |
| 3 | AI-Assisted Content Generation | Not Started | 2nd LLM provider not chosen | [module-3-ai-content-generation.md](./modules/module-3-ai-content-generation.md) |
| 4 | Fairness & Compliance | Not Started | — | [module-4-fairness-compliance.md](./modules/module-4-fairness-compliance.md) |
| 5 | Presentation Layer | Not Started | — | [module-5-presentation-layer.md](./modules/module-5-presentation-layer.md) |
| 6 | Scheduling Coordination | Not Started | Manus scope confirmation pending | [module-6-scheduling-coordination.md](./modules/module-6-scheduling-coordination.md) |
| 7 | Governance & Audit | Not Started | Named owner not assigned | [module-7-governance-audit.md](./modules/module-7-governance-audit.md) |

---

## 2. Pre-Build Decisions (block real work until answered)

These come from requirement.md §7 and design.md §10. Check off once decided — don't start the
affected module's build until its blocking item is resolved.

- [ ] Cloud platform (design.md §10.1)
- [ ] Second LLM provider for content generation (design.md §10.2) — blocks Module 3
- [ ] Manus scope confirmed: scheduling only, or scheduling + intake monitoring (design.md §10.3) — blocks Module 6
- [ ] Tech stack standard (design.md §10.4)
- [ ] Data residency confirmed by Legal/IT (design.md §10.5) — blocks Module 7 storage design
- [ ] Build vs. buy for resume parsing (design.md §10.6) — blocks Module 1
- [ ] Scale expectations (resumes/month, concurrent scheduling loops) (design.md §10.7)
- [ ] ATS/HRIS integration or greenfield (requirement.md §7.1)
- [ ] WhatsApp in this phase or deferred (requirement.md §7.2) — affects Module 1 scope
- [ ] Google Calendar required or Microsoft Graph only (requirement.md §7.3) — affects Module 6 scope
- [ ] Named operational owner assigned (requirement.md §7.4) — blocks Module 7
- [ ] JRP ownership assigned (requirement.md §7.5) — affects Module 2 rollout
- [ ] Legal/Compliance review of PDPO/GDPR/PIPL sections (requirement.md §7.6)
- [ ] Rollout sequencing: Workflow A before B, or together (requirement.md §7.7)
- [ ] Build vs. vendor vs. buy overall path (requirement.md §7.8)
- [ ] Discrimination-appeal retention window length (module-7 §6) — blocks Module 7 retention logic
- [ ] Hallucination-rate suspension threshold (module-3 §6) — blocks Module 3 audit process

---

## 3. Module 1 — Intake & Extraction

- [ ] Email intake adapter
- [ ] Teams intake adapter
- [ ] Malware/sandbox scanning
- [ ] Injection screening
- [ ] Manual-review queue
- [ ] Extraction: Skills / Projects / Experience / Education
- [ ] Confidence scoring per field
- [ ] Identity matching & dedup
- [ ] Parser version stamping
- [ ] 200-resume accuracy validation (≥95%)

## 4. Module 2 — Scoring Engine

- [ ] JRP data model
- [ ] Weight template presets + validation
- [ ] Must-have gating check
- [ ] Matching curves (Linear/Step/Buffered)
- [ ] Weighted score calculation + normalization
- [ ] Tier classification
- [ ] JRP change audit logging
- [ ] Scoring-engine version stamping
- [ ] One-round-one-version enforcement
- [ ] Rollback trigger hook

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
- [ ] Disparate-treatment review workflow
- [ ] PICS collection notice
- [ ] Separate talent-pool consent capture
- [ ] Retention auto-delete/anonymize job
- [ ] Consent-withdrawal deletion workflow
- [ ] Jurisdiction detection logic

## 7. Module 5 — Presentation Layer

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

- [ ] Audit Log data model
- [ ] Audit event emission from all modules
- [ ] Manual-review queue SLA monitoring
- [ ] Named owner assigned + wired
- [ ] Talent Pool tagging store
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
