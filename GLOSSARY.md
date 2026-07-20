# Glossary

Plain-language explanations of terms used throughout `md/`. Written for someone approaching this
project without prior context — if a term here doesn't match how it's used elsewhere, the docs are
wrong, not this file.

## Domain concepts

**JRP (Job Requirement Profile)** — the configuration HR sets up per job role: which criteria
matter (skills, experience, education, project relevance), how much each one is weighted, and which
ones are "must-have" vs. just "nice to have and scored." Every role gets its own JRP; there's no
single company-wide scoring formula.

**Must-have vs. weighted criteria** — a JRP criterion is either:
- **Must-have (gating)**: if a candidate doesn't meet it, they're disqualified — full stop, no
  score is computed.
- **Weighted (scored)**: contributes proportionally to the total score, doesn't disqualify by itself.

**Matching curve** — how partial credit is given on a weighted criterion. Example: a role wants 5
years of experience, a candidate has 4. Three ways to score that:
- **Linear**: 4/5 = 80% credit (proportional).
- **Step**: below the requirement = 0% (hard cutoff, no partial credit).
- **Buffered**: close-but-under still scores high (e.g., 90%), only drops off further below that.

**Tier** — after scoring, every candidate lands in **High Match (80–100%)**, **Mid Match
(60–79%)**, or **Low Match (below 60%)**. These are defaults — HR can adjust the cutoffs per JRP,
but the system ships with these numbers rather than an empty setting.

**Four-fifths rule** — a standard fairness check: if any demographic group's rate of advancing
past screening is less than 80% of the highest-advancing group's rate, that's flagged for a human
to investigate. It's a trigger for review, not proof of a problem and not something that
automatically changes anyone's score.

**PDPO** — Hong Kong's Personal Data (Privacy) Ordinance, the main privacy law this system is built
to comply with (analogous to GDPR in the EU). Drives the consent, retention, and access/correction
rules throughout.

**PICS** — "Personal Information Collection Statement," the formal notice given to a candidate at
intake explaining that an automated tool is involved and what happens to their data. A PDPO
requirement.

**Human-in-the-loop** — the system can score, rank, and flag candidates, but a human must explicitly
click "Pass" or "Reject" for anything to actually happen to a candidate's status. The system cannot
reject or advance anyone on its own, no matter the score.

## Project-specific terms

**Digital Employee** — the project's own name for this system: an AI-assisted "employee" that
handles resume screening and interview scheduling, but reports to and is overridden by human HR
staff at every consequential step.

**Workflow A / Workflow B** — the two halves of the system, named this way in the original SOP:
Workflow A is resume screening & scoring; Workflow B is interview scheduling coordination.

**Manus** — an autonomous AI agent product (distinct from a plain LLM API like Claude or GPT) used
in this design specifically to drive the *scheduling* workflow — checking calendars, polling
interviewers, following up with candidates. It does not touch scoring or candidate content; see
`md/design.md` §1.1 for why the split exists.

**"Second LLM provider"** — a separate, more conventional LLM API (which one exactly is still an
open decision) used only to generate the candidate summary, interview questions, and red-flag
hints. Deliberately kept separate from Manus and, more importantly, from the scoring engine.

**Stub-and-document** — the rule this project uses when a real-world decision (which cloud, which
LLM vendor, etc.) isn't made yet but code still needs to be written. Instead of guessing or
stalling, the code builds a clean interface and a working fake/local version behind it, and writes
down "here's what was assumed and why" in `ASSUMPTIONS.md` so a human can swap in the real thing
later without anything breaking in the meantime.

## Document/numbering conventions

**FR-# / NFR-#** — "Functional Requirement" / "Non-Functional Requirement," numbered in
`md/requirement.md`. Every other document (design, modules, tests) refers back to these numbers
instead of restating the requirement, so the numbers must stay stable — if you renumber one, every
file that cites it needs updating too.

**§ (section) references** — e.g. "design.md §3.4" means "design.md, numbered section 3.4." Used
throughout so any document can point at a specific part of another without duplicating its content.

**Module** — one of the 7 functional groupings the system is broken into for build tracking
(Intake & Extraction, Scoring Engine, AI-Assisted Content, Fairness & Compliance, Presentation,
Scheduling Coordination, Governance & Audit). See `md/modules/`.

**Wave** — in `md/prompt.md`, the build order groups modules into waves based on which modules
depend on which others (a module can't be built before the modules it depends on are done). Modules
in the same wave have no dependency on each other and can be built at the same time.

## Reading order

If you're new to this project, read in this order: this glossary → `README.md` → `md/requirement.md`
→ `md/design.md` → pick one `md/modules/module-N-*.md` file that interests you → `md/progress.md` to
see current status.
