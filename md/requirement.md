# HR Digital Employee — Requirements Document

**Status:** Draft for stakeholder review
**Audience:** HR leadership, Legal/Compliance, IT leadership
**Source:** HR Digital Employee SOP (Blueprint), Sections 1–7
**Scope:** Full system — Workflow A (Resume Screening & Scoring) and Workflow B (Interview Scheduling Coordination)

---

## 1. Purpose

This document translates the HR Digital Employee SOP into requirements suitable for stakeholder
sign-off before any build or vendor engagement begins. It states what the system must do, what it
must never do, what "done" looks like, and what remains open for decision.

---

## 2. Objectives (measurable)

| # | Objective | Target | Baseline method |
|---|---|---|---|
| O1 | Reduce manual resume data entry | 90% reduction in entry time per resume | 4-week manual-process measurement before go-live |
| O2 | Accelerate first-pass screening | Minutes → seconds per resume, 100% adherence to must-have criteria | Parser/scoring accuracy validated against 200 annotated resumes (95%+ field accuracy) |
| O3 | Reduce scheduling lead time | ≥50% reduction | Same 4-week baseline measurement, scheduling lead time |

All targets are **relative to a measured baseline**, not an assumed one — the baseline must be
captured before go-live and re-measured quarterly.

---

## 3. In Scope

### 3.1 Resume Screening & Scoring (Workflow A)
- Multi-channel resume intake: Email, Microsoft Teams (WhatsApp gated — see §7 Open Questions)
- Structured extraction: Skills, Projects, Working Experience, Education
- Weighted hard-criteria scoring against a per-role Job Requirement Profile (JRP)
- Candidate Summary Report: score, tier (High/Mid/Low Match), matching analysis, factual summary
- Decision support: suggested interview questions, red-flag detection
- Talent pool tagging and search
- Fairness / adverse-impact testing (four-fifths rule) against Hong Kong protected characteristics

### 3.2 Interview Scheduling Coordination (Workflow B)
- Calendar Free/Busy sync — **Microsoft 365 / Outlook / Exchange as primary** (Google Calendar as
  a secondary/future capability — see Open Questions)
- Consensus polling with internal interviewers
- Candidate-side confirmation step
- Automated, idempotent calendar event creation with time-zone handling
- Escalation to a human coordinator when no consensus is reached

### 3.3 Governance (cross-cutting, applies to both workflows)
- Human-in-the-loop: system never rejects, negotiates, or makes a final hiring decision
- Audit logging: actor, timestamp, reason, version, on every scoring and decision event
- Prompt-injection defense on all resume text before it reaches any LLM component
- PDPO-aligned candidate notification, explainability, access/correction, retention, and deletion
- Named operational owner, manual-review queue SLA, incident fallback to human-assisted mode

---

## 4. Out of Scope (explicitly, per SOP §1.3)

- Automated rejection emails/messages to candidates
- Salary or offer negotiation
- Automated conversational/chatbot screening interviews
- Final hiring decisions (system output is advisory/ranking only)

---

## 5. Functional Requirements

### 5.1 Data Ingestion & Extraction
- FR-1: System must ingest PDF resumes from designated Email inbox(es) and Microsoft Teams channels.
- FR-2: System must extract Skills, Projects, Experience, and Education as structured fields, each
  with a confidence score.
- FR-3: Any must-have field with confidence below 85% must route to manual review, never silently
  fail or auto-disqualify.
- FR-4: Unparseable files (image-only/encrypted PDFs) must route to a manual queue; candidate is
  notified and invited to resubmit.
- FR-5: System must deduplicate candidates across channels (email, phone, name+resume similarity);
  ambiguous matches go to a human, never auto-merge.

### 5.2 Scoring
- FR-6: HR must be able to define a Job Requirement Profile (JRP) per role, selecting a weight
  template (General, Senior technical, Junior/graduate, Managerial, Licensed/compliance) and
  fine-tuning weights (must sum to 100%).
- FR-7: Each criterion must be tagged must-have (gating) or weighted (scored).
- FR-8: Matching curve (Linear/Step/Buffered) must be configurable per dimension per role.
- FR-9: Scoring must be deterministic; LLM-assisted components (summary, interview questions) must
  never alter a score, tier, or gating outcome.
- FR-10: Every summary sentence must be traceable to a source passage in the resume (no
  unattributed/hallucinated content).

### 5.3 Presentation
- FR-11: System must produce notification cards (Email/Teams), a comparison table, and a web
  dashboard with filtering and drill-down.
- FR-12: System must generate suggested interview questions and red-flag highlights per candidate.

### 5.4 Decisioning
- FR-13: The system must never remove, reject, or filter a candidate based on score.
- FR-14: Advancement requires an explicit HR Pass/Reject action, logged with actor, timestamp, and
  reason.

### 5.5 Scheduling
- FR-15: System must read Free/Busy status for required interviewers via Microsoft Graph
  (least-privilege scope only).
- FR-16: System must identify 3–5 candidate slots, run an internal consensus poll, then a candidate
  confirmation step, before booking.
- FR-17: System must escalate to a human coordinator after 3 failed consensus rounds or if no
  overlapping availability exists within 7 days.
- FR-18: Calendar event creation must be idempotent and transactional (no duplicate or half-created
  events).
- FR-19: All times stored in UTC internally; displayed in each participant's local time zone.

### 5.6 Fairness & Compliance
- FR-20: System must run four-fifths adverse-impact testing per JRP, pre-deployment and at minimum
  quarterly thereafter.
- FR-21: Demographic data for fairness testing must be voluntary, self-declared, stored separately
  from scoring, and never used as a scoring input.
- FR-22: Candidates must receive a collection notice (PICS) at intake, with talent-pool consent as a
  separate, unbundled opt-in.
- FR-23: Non-hired candidate data auto-deletes/anonymizes at 24 months by default; withdrawal of
  consent triggers deletion within 30 days.

---

## 6. Non-Functional Requirements

- NFR-1: Parser field-level accuracy ≥95%, validated against ≥200 manually annotated resumes
  (scanned, mixed Chinese-English, unconventional layouts) before automatic gating is enabled.
- NFR-2: Manual-review queue items resolved within 1 business day (SLA-monitored, breach alerts
  the named owner).
- NFR-3: All inbound documents/messages treated as untrusted; scanned in isolation before parsing.
- NFR-4: Least-privilege access — Free/Busy scope only for discovery; event-creation rights limited
  to a dedicated service account.
- NFR-5: Every score records the scoring-engine and parser version that produced it; all candidates
  in one hiring round scored on the same version.
- NFR-6: Automatic rollback to human-assisted mode if core metrics degrade for two consecutive
  measurement periods, or parsing accuracy falls below threshold.

---

## 7. Open Questions (need answers before this doc can be finalized)

These are things I did not assume — please confirm or provide direction:

1. **ATS/HRIS integration** — marked "not sure yet." Does the org have an existing system of
   record for candidates (e.g., Workday, BambooHR, a homegrown tracker)? If yes, this system needs
   defined read/write integration points; if no, this system *is* the record and needs its own
   long-term data ownership plan.
2. **WhatsApp channel** — the SOP treats WhatsApp as gated behind Business API verification and
   template approval. Is WhatsApp intake a committed requirement for this phase, or deferred to a
   later phase (with Email + Teams as the initial channels)?
3. **Google Calendar** — since Microsoft 365 is primary, is dual-calendar support (Google + Microsoft)
   a real requirement (e.g., some interviewers use Gmail/Google Calendar), or can Workflow B be
   scoped to Microsoft Graph only for now?
4. **Named operational owner** — SOP §7 requires a specific accountable person for queues, alerts,
   and escalations. Who is this, or is this a role to be assigned before go-live?
5. **JRP ownership** — who defines and approves Job Requirement Profiles per role (HR generalists,
   hiring managers, a central recruiting ops function)?
6. **Legal/compliance review** — has Legal reviewed the PDPO/GDPR/PIPL sections (§4) yet, or should
   this document be the trigger for that review?
7. **Rollout sequencing** — should Workflow A (screening) go live before Workflow B (scheduling), or
   together? The SOP's rollback/baseline model (§6.1) implies independent measurement, which may
   argue for a phased rollout.
8. **Vendor vs. build** — this doc is for stakeholder alignment; once approved, will the next step be
   an internal build, a vendor RFP, or evaluation of an existing HR-tech platform that offers this
   out of the box?

---

## 8. Success Criteria for This Document

This requirements document is ready to move forward once:
- [ ] Open Questions in §7 are answered
- [ ] Legal/Compliance has reviewed §5.6 and §3.3 (governance/compliance requirements)
- [ ] A named operational owner is identified
- [ ] Leadership confirms the objectives in §2 and scope in §3–4
