# Module 1: Intake & Extraction

**Status:** Not Started
**Design source:** [design.md](../design.md) §3.1–3.3
**Requirement source:** [requirement.md](../requirement.md) FR-1–FR-5, NFR-1, NFR-3

---

## 1. Purpose

Receive resumes from designated channels, screen them for safety/trust, extract structured data,
and resolve candidate identity across submissions — the entry point for every candidate record in
the system.

## 2. Components Covered

| Component | Design ref | Responsibility |
|---|---|---|
| Ingestion Gateway | §3.1 | Receive Email/Teams (WhatsApp future) submissions; malware scan; injection screening; route unparseable files to manual queue |
| Extraction Service | §3.2 | Parse PDF resumes into Skills/Projects/Experience/Education with per-field confidence |
| Identity & Dedup Service | §3.3 | Match/merge candidate identity across channels; flag ambiguous matches to HR |

## 3. Requirements Covered

- **FR-1**: Ingest PDF resumes from Email and Teams
- **FR-2**: Extract structured fields with confidence scores
- **FR-3**: Must-have fields below 85% confidence route to manual review, never auto-disqualify --
  confidence is capped by the real OCR recognition confidence when a submission came from an
  image, not derived from text length alone (a 2026-07-23 fix; see below and ASSUMPTIONS.md)
- **FR-4**: Unparseable files route to manual queue; candidate notified to resubmit
- **FR-5**: Deduplicate across channels; ambiguous matches go to a human, never auto-merge
- **NFR-1**: Parser accuracy ≥95%, validated against ≥200 annotated resumes before automatic gating
- **NFR-3**: All inbound documents/messages treated as untrusted; scanned in isolation before parsing

## 4. Key Design Constraints

- A field that cannot be extracted is marked `Unverified` — never coerced to "Not Met."
- Field confidence reflects extraction *quality*, not just presence: for OCR'd images, Tesseract's
  own average per-word recognition confidence caps the score (`ocr.py`/`pdf_text.py`/
  `extraction.py`), so a section header that happened to OCR correctly followed by unreadable
  garbled content doesn't score as confidently as clean text just because it's long enough. A real
  PDF's text layer or plain-text passthrough has no such uncertainty and isn't capped (confirmed:
  ~0.41 confidence on a real, poorly-OCR'd resume template image vs. ~0.95-1.0 on clean/PDF/text
  input — see ASSUMPTIONS.md and `tests/test_pipeline.py`'s format-comparison tests).
- Hidden text (white-on-white, near-zero font, off-page content) and instruction-like patterns are
  stripped/detected before extraction output is finalized (feeds Module 3's injection defense, but
  the stripping itself happens here).
- Consistency guarantee: identical qualifications must produce identical outcomes regardless of
  resume format, layout, or language mix.
- Parser is versioned; every extraction output is stamped with the parser version (feeds Module 7).

## 5. Dependencies

- **Upstream:** none (entry point)
- **Downstream:** Module 2 (Scoring Engine) consumes structured extraction output; Module 7
  (Governance & Audit) receives intake/injection/dedup events for logging

## 6. Open Questions (from design.md §10)

- WhatsApp channel timing (requirement.md §7.2) — affects whether this module needs a WhatsApp
  adapter in this phase or a later one.
- Build vs. buy for parsing (design.md §10.6) — **PDF byte-to-text extraction resolved**: built,
  using `pypdf` (`intake_extraction/pdf_text.py`; ASSUMPTIONS.md). **Image OCR resolved on the
  free/offline side only**: built, using local Tesseract (`intake_extraction/ocr.py`); cloud OCR
  (Azure AI Document Intelligence/AWS Textract) remains open, and ASSUMPTIONS.md records an
  observed (not theoretical) accuracy gap between the two on real resume layouts. Still open:
  whether the structured Skills/Projects/Experience/Education splitting stays a regex heuristic or
  moves to a managed document-intelligence API/custom NLP model.

## 7. Progress Checklist

- [ ] Email intake adapter
- [ ] Teams intake adapter
- [ ] Malware/sandbox scanning
- [ ] Injection screening (hidden text, instruction-pattern detection)
- [ ] Manual-review queue (unparseable files, low-confidence fields)
- [ ] Extraction: Skills
- [ ] Extraction: Projects
- [ ] Extraction: Working Experience
- [ ] Extraction: Education
- [x] Confidence scoring per field — length-based, capped by real OCR recognition confidence for
      image submissions (not a length-only guess for OCR'd content)
- [ ] Identity matching (email/phone/name+resume similarity)
- [ ] Auto-merge on confident match; flag-to-human on ambiguous match
- [ ] Parser version stamping
- [ ] 200-resume accuracy validation set assembled and passed (≥95%)

## 8. Testing

See [test.md](../test.md) §1 for module-specific test steps.
