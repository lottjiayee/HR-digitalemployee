# Module 3: AI-Assisted Content Generation

**Status:** In Progress — summary/questions/red-flags built, rough draft (see md/progress.md)
**Design source:** [design.md](../design.md) §3.5, §1.1
**Requirement source:** [requirement.md](../requirement.md) FR-10, FR-12

---

## 1. Purpose

Generate the factual candidate summary, suggested interview questions, and red-flag hints — the
system's only LLM-generation surface. Architecturally isolated from scoring so it can never
influence a candidate's outcome.

## 2. Components Covered

| Component | Design ref | Responsibility |
|---|---|---|
| LLM-Assisted Service | §3.5 | Summary generation, interview question suggestions, red-flag highlighting |

**AI provider:** second LLM provider — **not yet chosen** (design.md §10.2). This module is a
single-shot, tightly-scoped API integration, not an autonomous agent (Manus is out of scope here —
see Module 6).

## 3. Requirements Covered

- **FR-10**: Every summary sentence traceable to a source passage; unanchored sentences dropped
- **FR-12**: Generate suggested interview questions and red-flag highlights per candidate

## 4. Key Design Constraints

- Input is **structured extraction output only** (Module 1) — raw resume free text is never
  supplied as instructions or context that could alter output framing.
- Output writes only to summary/question/flag fields — no code path from this service to
  score/tier/gating tables (enforced by Module 2's isolation, not by this module's discipline
  alone).
- Sentence-level anchoring is mandatory: a generated sentence without an identifiable source
  passage is not emitted.
- Monthly sampled hallucination audit (manual comparison of summaries vs. source resumes) is an
  operational process this module must support with a query/export hook, not something the module
  performs itself.
- Interview questions cover three angles: verification (probe high-scoring areas), gap analysis
  (missing/low-scoring areas), behavioral (inferred from project/experience descriptions).
- Red flags: inconsistencies (dates/roles), keyword-stuffing without substance, frequent job
  changes — but per Module 4's fairness mitigations, gap/tenure-based flags must be framed as
  neutral clarification items, not automatic penalties.

## 5. Dependencies

- **Upstream:** Module 1 (structured extraction), Module 2 (score/tier context for question
  targeting)
- **Downstream:** Module 5 (Presentation displays summary/questions/flags)

## 6. Open Questions

- **Which second LLM provider** (Claude, OpenAI, Azure OpenAI, other) — design.md §10.2, unresolved.
- Hallucination-rate threshold that triggers suspension (design.md/SOP 2.3.1 references "the agreed
  threshold" without a number) — needs a concrete figure before the audit process can run.

## 7. Progress Checklist

- [ ] LLM provider selected and API integration built — stubbed with a deterministic offline
      `TemplateLLMProvider`; real vendor choice still open (design.md §10.2, ASSUMPTIONS.md)
- [x] Prompt/pipeline: structured-input-only enforcement (no raw resume text passthrough) —
      enforced by the function signatures themselves, no raw-text parameter exists anywhere
- [x] Summary generation (3–5 sentences, factual)
- [x] Sentence-level source anchoring + drop-unanchored-sentence logic
- [x] Interview question generation (verification / gap / behavioral)
- [x] Red-flag detection (inconsistencies, keyword-stuffing, job-change patterns)
- [x] Red-flag framing reviewed against Module 4 fairness mitigations (gaps = neutral, not penalty)
- [x] Model/prompt version stamping on generated content — applies to the LLM-generated
      `CandidateSummary` only; interview questions and red flags are deterministic rule-based
      logic with no model/prompt to version (see ASSUMPTIONS.md)
- [x] Monthly hallucination-audit export/sampling hook
- [ ] Hallucination-rate threshold defined and suspension logic wired — suspension mechanism is
      built and tested; no agreed threshold number exists yet to default it to (ASSUMPTIONS.md)

## 8. Testing

See [test.md](../test.md) §3 for module-specific test steps.
