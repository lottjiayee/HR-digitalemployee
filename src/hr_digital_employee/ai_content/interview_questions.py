"""Interview question generation (design.md §3.5, FR-12; module-3 doc §4): three angles --
verification (probe high-scoring areas), gap analysis (probe missing/low-scoring areas), and
behavioral (inferred from project/experience descriptions).

Reads Module 2's `Score.breakdown` for targeting -- never writes to it, and never re-derives a
score (that stays Module 2's job alone, per FR-9's separation).
"""

from __future__ import annotations

from hr_digital_employee.ai_content.models import InterviewQuestion, QuestionAngle
from hr_digital_employee.intake_extraction.interfaces import ExtractedResume, FieldStatus
from hr_digital_employee.scoring_engine.interfaces import Dimension, Score

HIGH_SCORE_THRESHOLD = 0.85
"""A dimension's curve_score at or above this is a strength worth probing (verification angle)."""

LOW_SCORE_THRESHOLD = 0.5
"""A dimension's curve_score at or below this is a gap worth probing (gap angle)."""

_DIMENSION_LABELS: dict[Dimension, str] = {
    Dimension.MANDATORY_SKILLS: "your listed skills",
    Dimension.EXPERIENCE_TENURE: "your work experience",
    Dimension.EDUCATIONAL_LEVEL: "your educational background",
    Dimension.PROJECT_RELEVANCE: "your project work",
}


def _verification_question(label: str) -> InterviewQuestion:
    return InterviewQuestion(
        angle=QuestionAngle.VERIFICATION,
        text=f"You scored strongly on {label} -- can you walk through a specific example that "
        "demonstrates this?",
    )


def _gap_question(label: str) -> InterviewQuestion:
    return InterviewQuestion(
        angle=QuestionAngle.GAP,
        text=f"Your profile shows {label} below this role's target -- how would you approach "
        "closing that gap?",
    )


def generate_interview_questions(
    score: Score, extracted: ExtractedResume
) -> tuple[InterviewQuestion, ...]:
    """module-3 doc §4: questions cover verification/gap/behavioral angles. Every dimension
    clearing `HIGH_SCORE_THRESHOLD`/`LOW_SCORE_THRESHOLD` gets its own targeted question; if none
    does (a candidate scoring in the broad middle band on every dimension -- not a rare case,
    since 60-79% is the entire Mid Match tier), the strongest/weakest dimension by relative rank is
    still asked about, so verification and gap coverage isn't left to chance on a threshold gap."""
    questions: list[InterviewQuestion] = []
    verification_asked = False
    gap_asked = False

    for result in score.breakdown:
        label = _DIMENSION_LABELS[result.dimension]
        if result.curve_score >= HIGH_SCORE_THRESHOLD:
            questions.append(_verification_question(label))
            verification_asked = True
        elif result.curve_score <= LOW_SCORE_THRESHOLD:
            questions.append(_gap_question(label))
            gap_asked = True

    if score.breakdown:
        # Ranked (not separate max()/min() calls): when every dimension ties at the same
        # mid-range score, max() and min() both resolve to the *first* tied element (Python's tie-
        # break is "first occurrence" for both), so a second tied dimension was silently dropped
        # from consideration entirely -- sorting once and taking the two ends gives each of two
        # tied dimensions its own distinct entry instead.
        ranked = sorted(score.breakdown, key=lambda r: r.curve_score)
        weakest = ranked[0]
        strongest = ranked[-1]
        # Guarded by more than "not verification_asked"/"not gap_asked": if every dimension
        # already cleared the *opposite* threshold (e.g. every dimension is a strength), the
        # fallback's own candidate would be a dimension that already got that opposite-angle
        # question -- asking about it again from this angle would be self-contradictory (e.g. "you
        # scored strongly" and "your profile shows a gap" about the same dimension). In that case
        # there's genuinely nothing left in the "opposite" direction to probe, so it's skipped
        # rather than forced.
        ask_verification = not verification_asked and strongest.curve_score > LOW_SCORE_THRESHOLD
        ask_gap = not gap_asked and weakest.curve_score < HIGH_SCORE_THRESHOLD
        if strongest.dimension == weakest.dimension and ask_verification and ask_gap:
            # Only one dimension survives to fall back on (a single-dimension JRP, or every
            # dimension tied at the identical mid-range score) -- asking both angles about the
            # exact same dimension is the identical self-contradiction the guard above is meant to
            # prevent, just reached a different way. Pick whichever angle it sits closer to instead
            # of asking both.
            midpoint = (LOW_SCORE_THRESHOLD + HIGH_SCORE_THRESHOLD) / 2
            if strongest.curve_score >= midpoint:
                ask_gap = False
            else:
                ask_verification = False
        if ask_verification:
            questions.append(_verification_question(_DIMENSION_LABELS[strongest.dimension]))
        if ask_gap:
            questions.append(_gap_question(_DIMENSION_LABELS[weakest.dimension]))

    questions.append(
        InterviewQuestion(angle=QuestionAngle.BEHAVIORAL, text=_behavioral_question(extracted))
    )
    return tuple(questions)


def _behavioral_question(extracted: ExtractedResume) -> str:
    if extracted.projects.status is FieldStatus.VERIFIED and extracted.projects.value:
        first_project = extracted.projects.value[0]
        return (
            f'Tell me more about "{first_project}" -- what was your specific role, and what '
            "challenges did you encounter?"
        )
    if extracted.experience.status is FieldStatus.VERIFIED and extracted.experience.value:
        return (
            "Walk me through a challenging situation from your work experience and how you "
            "handled it."
        )
    return "Tell me about a challenging situation you've faced and how you handled it."
