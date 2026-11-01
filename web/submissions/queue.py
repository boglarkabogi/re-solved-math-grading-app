"""The work queue: putting model runs in line and taking them out again.

The view never calls a model. It writes a Job row and answers at once; a
separate worker process (``manage.py run_worker``) picks the rows up in the
order they arrived. Everything that decides *which* job runs next lives here,
so the rules can be tested without HTTP and without a worker.
"""

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Job

logger = logging.getLogger(__name__)


def workers():
    """How many jobs may run at the same time."""
    return max(1, int(getattr(settings, "QUEUE_WORKERS", 3)))


def seconds_per_job():
    """Rough length of one model run, used only for the estimate shown to students."""
    return max(1, int(getattr(settings, "QUEUE_SECONDS_PER_JOB", 25)))


def enqueue(submission, kind):
    """Put one job in line, unless the same work is already waiting or running.

    Returns the Job row. A double click, or a reloaded page, must not put the
    same submission in the queue twice - that would spend two model calls and
    charge the same student's work twice.
    """
    with transaction.atomic():
        existing = (
            Job.objects.select_for_update()
            .filter(
                submission=submission,
                kind=kind,
                state__in=[Job.State.QUEUED, Job.State.RUNNING],
            )
            .first()
        )

        if existing is not None:
            logger.info(
                "The job is already in the queue: submission=%s kind=%s job=%s",
                submission.id,
                kind,
                existing.id,
            )
            return existing

        job = Job.objects.create(submission=submission, kind=kind)

    logger.info("Job queued: submission=%s kind=%s job=%s", submission.id, kind, job.id)

    return job


def claim(worker_name):
    """Take the oldest waiting job, or return None when the queue is empty.

    Several workers run at once, so taking a job has to be a single atomic
    step: the UPDATE only succeeds for the worker that gets there first, and
    the others simply move on to the next row. This works the same on SQLite
    and on PostgreSQL, unlike row locking.
    """
    for job in Job.objects.filter(state=Job.State.QUEUED).order_by("queued_at", "id")[:20]:
        taken = Job.objects.filter(pk=job.pk, state=Job.State.QUEUED).update(
            state=Job.State.RUNNING,
            started_at=timezone.now(),
            attempts=job.attempts + 1,
            worker=worker_name[:80],
        )

        if taken:
            job.refresh_from_db()
            return job

    return None


def finish(job, error=""):
    """Close a job, either as done or as failed."""
    job.state = Job.State.FAILED if error else Job.State.DONE
    job.finished_at = timezone.now()
    job.error = error[:2000]
    job.save(update_fields=["state", "finished_at", "error"])

    logger.info(
        "Job finished: job=%s kind=%s state=%s seconds=%s",
        job.id,
        job.kind,
        job.state,
        job.duration_seconds,
    )

    return job


def position(job):
    """Where this job stands in line, counting from 1.

    A running job is 1: it is being worked on. A waiting job counts everything
    that is ahead of it, which is every running job plus every job queued
    earlier.
    """
    if job.state == Job.State.RUNNING:
        return 1

    if job.state != Job.State.QUEUED:
        return 0

    ahead = Job.objects.filter(state=Job.State.RUNNING).count()

    ahead += (
        Job.objects.filter(state=Job.State.QUEUED)
        .filter(queued_at__lt=job.queued_at)
        .exclude(pk=job.pk)
        .count()
    )

    return ahead + 1


def wait_seconds(place):
    """Rough wait for a job standing at ``place``, with ``workers()`` running at once.

    Deliberately a rough number: it is there so the student can see the queue
    moving, not so they can set a timer by it.
    """
    if place <= 0:
        return 0

    rounds = (place + workers() - 1) // workers()

    return rounds * seconds_per_job()
