"""What the worker actually runs for each queued job.

The view used to do this inline, which is why a single model call could hold
up a web worker for half a minute. Here it is free of HTTP: no request, no
messages, no redirects - so it can be run by the worker and tested directly.
"""

import logging

from django.db import transaction
from django.db.models import F

from motor.recognition.service import recognise_solution

from .models import Job, Submission
from .services import run_grading

logger = logging.getLogger(__name__)


def run(job):
    """Run one job. Raises on failure; the worker records that on the Job row."""
    if job.kind == Job.Kind.OCR:
        return run_ocr(job.submission)

    if job.kind == Job.Kind.GRADING:
        return run_evaluation(job.submission)

    raise ValueError(f"Unknown job kind: {job.kind!r}")


def run_ocr(submission):
    """Recognise the handwriting on the newest uploaded image.

    The recognition slot was already reserved by the view, so the attempt
    counter and the 3-run limit are settled before we get here. A failed run
    does not count against the student: the state goes back to IMAGE_UPLOADED
    and the counter is left alone.
    """
    ocr_attempt = submission.ocr_attempts.order_by("-created_at").first()

    if ocr_attempt is None:
        raise ValueError("The submission has no uploaded image.")

    task = submission.assignment.task

    logger.info(
        "Recognition started: submission=%s ocr_attempt=%s run=%s",
        submission.id,
        ocr_attempt.id,
        submission.ocr_run_count + 1,
    )

    try:
        result = recognise_solution(
            image_field=ocr_attempt.image,
            task_text=task.task_text,
        )

        text = result["text"]
        model_name = result["model_name"]

        if not isinstance(text, str) or not text.strip():
            raise ValueError("OCR returned empty or invalid text.")

        if not isinstance(model_name, str):
            raise ValueError("OCR returned an invalid model name.")

    except Exception:
        logger.exception(
            "Recognition failed: submission=%s ocr_attempt=%s",
            submission.id,
            ocr_attempt.id,
        )

        # A failed run must not cost the student one of their three attempts.
        Submission.objects.filter(pk=submission.pk).update(
            state=Submission.State.IMAGE_UPLOADED,
            ocr_in_progress=False,
        )

        raise

    with transaction.atomic():
        ocr_attempt.ocr_text = text
        ocr_attempt.model_name = model_name
        ocr_attempt.save(update_fields=["ocr_text", "model_name"])

        Submission.objects.filter(pk=submission.pk).update(
            state=Submission.State.OCR_DONE,
            ocr_run_count=F("ocr_run_count") + 1,
            ocr_in_progress=False,
        )

    submission.refresh_from_db(fields=["state", "ocr_run_count", "ocr_in_progress"])

    logger.info(
        "Recognition saved: submission=%s ocr_attempt=%s run_count=%s model=%s",
        submission.id,
        ocr_attempt.id,
        submission.ocr_run_count,
        model_name,
    )

    return ocr_attempt


def run_evaluation(submission):
    """Grade the recognised text.

    run_grading already writes the Evaluation row and moves the submission to
    GRADED or FAILED, so there is nothing to undo here: a run that gives no
    usable score is a finished run with a failed result, not a lost job.
    """
    ocr_attempt = submission.ocr_attempts.order_by("-created_at").first()

    if ocr_attempt is None or not ocr_attempt.ocr_text:
        raise ValueError("The submission has no recognised text to evaluate.")

    return run_grading(submission, ocr_attempt)
