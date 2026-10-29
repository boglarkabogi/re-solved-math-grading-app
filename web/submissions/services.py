"""Running the grading engine on a submission and storing its result.

The view only decides *whether* to grade. Everything about *how* a result
becomes an Evaluation row lives here, so it can be tested without HTTP.
"""

import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction

from motor import grading

from .models import Evaluation, Submission

logger = logging.getLogger(__name__)

RESULT_KEYS = {
    "score": "pont",
    "reasoning": "indoklas",
    "confidence": "magabiztossag",
    "ocr_error_suspected": "ocr_hiba_gyanu",
    "ocr_error_reason": "ocr_hiba_indok",
    "interpretable": "ertelmezheto",
    "student_final_answer": "diak_vegeredmenye",
    "score_was_snapped": "pont_kerekitve",
    "raw_response": "nyers_valasz",
    "prompt": "prompt",
    "model_name": "modell",
}


def run_grading(submission, ocr_attempt):
    """Grade one submission and return the stored Evaluation.

    Only the task, the reference solution, the recognised text and the
    student's own note are sent to the model - never a name, an e-mail address
    or any other personal data.

    Returns the Evaluation row. A row is written even when the model gave no
    usable score: then the submission ends up FAILED and flagged for the
    teacher, so nothing is silently lost.
    """
    task = submission.assignment.task

    submission.state = Submission.State.GRADING
    submission.save(update_fields=["state"])

    try:
        result = grading.grade(
            task.task_text,
            task.correct_solution,
            ocr_attempt.ocr_text,
            submission.student_note or None,
        )
    except Exception:
        logger.exception("The grading engine raised: submission=%s", submission.id)
        submission.state = Submission.State.FAILED
        submission.needs_review = True
        submission.save(update_fields=["state", "needs_review"])
        return None

    return _store(submission, result)


def _field(result, name):
    """Read one field of the engine's answer by its English name.

    A name that RESULT_KEYS does not map, or that the model left out, reads as
    None instead of raising: a changed prompt must not take the page down.
    """
    key = RESULT_KEYS.get(name)
    if key is None:
        logger.warning("RESULT_KEYS has no entry for %r", name)
        return None
    return result.get(key)


def _store(submission, result):
    score = _as_score(_field(result, "score"))
    score_was_snapped = bool(_field(result, "score_was_snapped"))
    ocr_error_suspected = bool(_field(result, "ocr_error_suspected"))
    interpretable = _field(result, "interpretable")
    unreadable = interpretable is False

    with transaction.atomic():
        evaluation = Evaluation.objects.create(
            submission=submission,
            model_name=result.get(RESULT_KEYS["model_name"]) or "",
            score=score,
            reasoning=result.get(RESULT_KEYS["reasoning"]) or "",
            confidence=_as_confidence(result.get(RESULT_KEYS["confidence"])),
            ocr_error_suspected=ocr_error_suspected or unreadable,
            ocr_error_reason=_field(result, "ocr_error_reason") or "",
            student_final_answer=_field(result, "student_final_answer") or "",
            raw_response=result.get(RESULT_KEYS["raw_response"]) or "",
            prompt=result.get(RESULT_KEYS["prompt"]) or "",
        )

        if score is None:
            submission.state = Submission.State.FAILED
            submission.needs_review = True
        else:
            submission.state = Submission.State.GRADED
            submission.needs_review = (
                submission.needs_review or ocr_error_suspected or unreadable or score_was_snapped
            )

        submission.save(update_fields=["state", "needs_review"])

    logger.info(
        "Evaluation stored: submission=%s evaluation=%s score=%s model=%s",
        submission.id,
        evaluation.id,
        score,
        evaluation.model_name,
    )

    return evaluation


def _as_score(value):
    """Turn the engine's score into a Decimal, or None.

    The scoring scale is the engine's business, not ours: motor.parsing has
    already moved the score onto one of the five allowed values, or set it to
    None when the model answered outside 0..1. Here we only convert, so the
    rule lives in exactly one place.
    """
    if value is None or value == "":
        return None

    try:
        score = Decimal(str(value))
    except (InvalidOperation, ValueError):
        logger.warning("The model returned an unusable score: %r", value)
        return None

    return score.quantize(Decimal("0.01"))


def _as_confidence(value):
    """Turn the model's confidence into a 0..100 integer, or None."""
    if value is None or value == "":
        return None

    try:
        confidence = int(round(float(value)))
    except (TypeError, ValueError):
        return None

    return max(0, min(100, confidence))
