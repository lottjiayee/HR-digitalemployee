# Module 5: Presentation Layer

**Status:** In Progress -- comparison table + drill-down dashboard built, rough draft
**Design source:** [design.md](../design.md) §3.7–3.8
**Requirement source:** [requirement.md](../requirement.md) FR-11, FR-13, FR-14

---

## 1. Purpose

Surface candidate scores/summaries to HR through notification cards, comparison tables, and a
dashboard — and provide the **only** interface through which a candidate's status can actually
change.

## 2. Components Covered

| Component | Design ref | Responsibility |
|---|---|---|
| Notification Service | §3.7 | Render/deliver notification cards to Email/Teams (and scheduling messages, shared with Module 6) |
| Dashboard / API | §3.8 | Pipeline overview, filtering, drill-down, JRP configuration UI, fairness-flag review UI, Pass/Reject action |

## 3. Requirements Covered

- **FR-11**: Notification cards (Email/Teams), comparison table, web dashboard with filtering/drill-down
- **FR-13**: System never removes/rejects/filters a candidate based on score
- **FR-14**: Advancement requires explicit HR Pass/Reject action, logged with actor/timestamp/reason

## 4. Key Design Constraints

- This is the **only** component with a write path to candidate status — no other module may
  change an application's Pass/Reject state.
- Score is presented for ranking/prioritization only; UI must not imply or enable automatic
  filtering-out of low scorers (e.g., no "auto-hide below X%" default that functions as a rejection).
- Dashboard surfaces: total applicants, average score, pipeline stage distribution, filtering by
  score/skills/experience/source, skill-gap visualizations.
- Notification card format must respect each channel's constraints (Teams card format now;
  WhatsApp interactive-message limits when that channel is added — Teams/Email are the fallback
  when WhatsApp's layout can't be reproduced).
- Every Pass/Reject action is captured with actor, timestamp, and a stated reason — no anonymous or
  reason-less status changes.

## 5. Dependencies

- **Upstream:** Module 2 (scores/tiers), Module 3 (summaries/questions/red flags), Module 4
  (fairness flags for JRP-owner review)
- **Downstream:** Module 6 (Pass/shortlist action triggers the scheduling loop), Module 7 (every
  Pass/Reject and JRP-config action logged)

## 6. Open Questions

- None specific beyond the general tech-stack question in design.md §10.4 (frontend framework
  choice).

## 7. Progress Checklist

- [ ] Notification card rendering (Email)
- [ ] Notification card rendering (Teams)
- [x] Detailed comparison table view -- `presentation/app.py` (Streamlit, `hr-digital-employee-
      dashboard` console script), read-only, over the same Modules 1+2+3 pipeline as the CLI
      report; see ASSUMPTIONS.md for exactly what this first slice does and doesn't cover
- [ ] Dashboard: pipeline overview (totals, average score, stage distribution)
- [ ] Dashboard: filtering (score range, skills, experience, source)
- [x] Dashboard: candidate drill-down (full report; original resume file itself not shown, only
      its extracted fields -- see ASSUMPTIONS.md)
- [ ] Dashboard: skill-gap / applicant-pool visualizations
- [ ] JRP configuration UI (weights, must-have flags, curves) -- `jrp_editor/` covers this today
      as a separate, not-yet-merged-into-this-dashboard tool (see module doc)
- [ ] Fairness-flag review UI (surfaces Module 4 flags to JRP owners)
- [ ] Explicit Pass/Reject action (with mandatory reason field)
- [ ] Decision logging on every Pass/Reject (actor, timestamp, reason)
- [x] UI/UX review confirming no path exists to auto-filter by score -- this slice has no
      filtering of any kind yet, so the constraint holds trivially; re-verify when filtering
      (above) is built

## 8. Testing

See [test.md](../test.md) §5 for module-specific test steps.
