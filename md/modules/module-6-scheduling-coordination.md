# Module 6: Scheduling Coordination

**Status:** Not Started
**Design source:** [design.md](../design.md) §3.9–3.10, §1.1
**Requirement source:** [requirement.md](../requirement.md) FR-15–FR-19

---

## 1. Purpose

Find an interview time that works for all required interviewers and the candidate, then book it
automatically — the system's one agent-executed workflow.

## 2. Components Covered

| Component | Design ref | Responsibility |
|---|---|---|
| Scheduling Coordinator | §3.9 | Consensus-then-confirmation state machine: slot discovery, internal poll, candidate confirmation, retry/escalate |
| Calendar Adapter | §3.10 | Unified Free/Busy + booking interface over Microsoft Graph (primary); Google Calendar structurally supported but not required |

**Execution model:** the step-by-step work (checking availability, sending polls, waiting on
responses, retrying) is carried out by the **Manus agent** (design.md §1.1), operating only through
this module's defined tool interfaces. The state machine — retry counts, timeouts, escalation
triggers — is deterministic and owned by this module; Manus executes within those bounds and cannot
unilaterally extend a deadline or skip an escalation.

## 3. Requirements Covered

- **FR-15**: Read Free/Busy via Microsoft Graph, least-privilege scope only
- **FR-16**: Identify 3–5 slots → internal consensus poll → candidate confirmation → booking
- **FR-17**: Escalate to human coordinator after 3 failed rounds or no availability within 7 days
- **FR-18**: Idempotent, transactional calendar event creation (no duplicates/half-created state)
- **FR-19**: UTC internal storage; local-time display per participant

## 4. Key Design Constraints

- Required vs. optional participants: "majority consensus" applies only to optional participants;
  any required participant's unavailability invalidates a slot.
- Candidate-side timeout: 72 hours + one reminder, then 48 more hours before releasing held slots
  and notifying HR — the loop is symmetric, neither side can stall it indefinitely.
- Slot soft-locking: a slot sent for candidate confirmation is locked (TTL = confirmation window)
  against other scheduling loops, to prevent double-booking.
- Retry with state change: each unsuccessful round increments retry count, widens the search
  window, and excludes previously rejected slots — never regenerates the same slots.
- Manus is scoped to the Calendar Adapter and Notification Service tool interfaces only — no raw
  calendar-provider or database credentials; every agent action is audit-logged (feeds Module 7).

## 5. Dependencies

- **Upstream:** Module 5 (HR shortlist/Pass action triggers scheduling), Module 7 (audit logging
  for every agent action)
- **Downstream:** Module 5 (Notification Service delivers polls/confirmations), Module 7 (booking
  events, escalations logged)

## 6. Open Questions

- **Manus scope confirmation** (design.md §10.3) — confirm Manus should also cover intake channel
  monitoring, or stay scoped to scheduling only.
- **Google Calendar necessity** (requirement.md §7.3) — Microsoft Graph only vs. true dual-calendar.

## 7. Progress Checklist

- [ ] Microsoft Graph OAuth2 integration (Free/Busy scope)
- [ ] Google Calendar OAuth2 integration (if confirmed needed — see Open Questions)
- [ ] Unified Free/Busy abstraction layer over both providers
- [ ] UTC-internal / local-time-display time-zone handling
- [ ] Slot discovery algorithm (3–5 slots, clustering to minimize context-switching)
- [ ] Internal consensus poll (required vs. optional participant logic)
- [ ] Vote-timeout handling (treat as no-consensus, continue loop)
- [ ] Retry/widen/exclude-rejected-slots state machine
- [ ] Candidate confirmation step + reschedule re-entry
- [ ] Candidate-side timeout (72h reminder + 48h release)
- [ ] Slot soft-locking (TTL = confirmation window)
- [ ] Human escalation trigger (3 rounds / 7-day no-availability)
- [ ] Idempotent, transactional dual-calendar booking (rollback on partial failure)
- [ ] Manus agent integration scoped to Calendar Adapter + Notification Service tool interfaces only
- [ ] Agent-action audit logging wired to Module 7

## 8. Testing

See [test.md](../test.md) §6 for module-specific test steps.
