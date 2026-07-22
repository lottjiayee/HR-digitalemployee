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
        if not verification_asked:
            strongest = max(score.breakdown, key=lambda r: r.curve_score)
            questions.append(_verification_question(_DIMENSION_LABELS[strongest.dimension]))
        if not gap_asked:
            weakest = min(score.breakdown, key=lambda r: r.curve_score)
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
