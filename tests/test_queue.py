"""The work queue: what goes in line, in what order, and what the student sees.

The model calls used to run inside the request. A class of students pressing
the button at the same time would have tied up every web worker, so the runs
now wait in a queue and a separate worker process takes them.
"""

import pytest
from django.urls import reverse

from courses.models import Member
from submissions import queue
from submissions.models import Evaluation, Job, Submission


def status_url(world):
    return reverse(
        "job_status",
        kwargs={"group_id": world["group"].id, "lesson_id": world["lesson"].id},
    )


# --- putting work in line ---------------------------------------------------


@pytest.mark.django_db
def test_posting_queues_the_work_instead_of_calling_the_model(client, world, calls):
    """The point of the whole change: the request returns without a model call."""
    client.force_login(world["student"])

    client.post(world["url"])

    assert calls["recorded"] == []
    job = Job.objects.get(submission=world["submission"])
    assert job.kind == Job.Kind.GRADING
    assert job.state == Job.State.QUEUED
    assert Evaluation.objects.count() == 0


@pytest.mark.django_db
def test_the_submission_is_marked_as_being_evaluated(client, world, calls):
    """So a reload shows the waiting page rather than the start button again."""
    client.force_login(world["student"])

    client.post(world["url"])

    world["submission"].refresh_from_db()
    assert world["submission"].state == Submission.State.GRADING


@pytest.mark.django_db
def test_a_double_click_does_not_queue_the_work_twice(client, world, calls, work_queue):
    """Two jobs would mean two model calls, and the student's work graded twice."""
    client.force_login(world["student"])

    client.post(world["url"])
    client.post(world["url"])

    assert Job.objects.filter(submission=world["submission"]).count() == 1

    work_queue()
    assert len(calls["recorded"]) == 1


@pytest.mark.django_db
def test_two_students_each_get_their_own_place(client, world, make_student, calls):
    """The queue is shared, but one student's work is never merged with another's."""
    client.force_login(world["student"])
    client.post(world["url"])

    assert Job.objects.count() == 1
    assert Job.objects.first().submission == world["submission"]


# --- the order of the queue -------------------------------------------------


@pytest.mark.django_db
def test_the_queue_is_served_in_the_order_it_was_filled(world):
    first = queue.enqueue(world["submission"], Job.Kind.OCR)
    queue.finish(first)

    second = queue.enqueue(world["submission"], Job.Kind.GRADING)

    taken = queue.claim("worker-1")

    assert taken.id == second.id


@pytest.mark.django_db
def test_a_job_is_only_taken_once(world):
    """Several workers run at the same time; two must never get the same job."""
    queue.enqueue(world["submission"], Job.Kind.GRADING)

    first = queue.claim("worker-1")
    second = queue.claim("worker-2")

    assert first is not None
    assert second is None


@pytest.mark.django_db
def test_claiming_records_who_took_it_and_when(world):
    queue.enqueue(world["submission"], Job.Kind.GRADING)

    job = queue.claim("gep#2")

    assert job.state == Job.State.RUNNING
    assert job.worker == "gep#2"
    assert job.started_at is not None
    assert job.attempts == 1


@pytest.mark.django_db
def test_an_empty_queue_gives_nothing_back(world):
    assert queue.claim("worker-1") is None


# --- position and estimate --------------------------------------------------


@pytest.mark.django_db
def test_the_first_waiting_job_is_number_one(world):
    job = queue.enqueue(world["submission"], Job.Kind.GRADING)

    assert queue.position(job) == 1


@pytest.mark.django_db
def test_a_running_job_counts_as_the_front_of_the_queue(world):
    queue.enqueue(world["submission"], Job.Kind.GRADING)
    job = queue.claim("worker-1")

    assert queue.position(job) == 1


@pytest.mark.django_db
def test_a_finished_job_is_not_in_the_queue_any_more(world):
    job = queue.enqueue(world["submission"], Job.Kind.GRADING)
    queue.finish(job)

    assert queue.position(job) == 0


@pytest.mark.django_db
def test_the_estimate_divides_the_queue_between_the_workers(settings):
    settings.QUEUE_WORKERS = 3
    settings.QUEUE_SECONDS_PER_JOB = 25

    # Az első három egyszerre megy, tehát mindhárom egy kör.
    assert queue.wait_seconds(1) == 25
    assert queue.wait_seconds(3) == 25
    # A negyedik már a második körben, tehát két kör.
    assert queue.wait_seconds(4) == 50
    assert queue.wait_seconds(0) == 0


@pytest.mark.django_db
def test_one_worker_makes_the_queue_strictly_sequential(settings):
    settings.QUEUE_WORKERS = 1
    settings.QUEUE_SECONDS_PER_JOB = 20

    assert queue.wait_seconds(4) == 80


# --- failures ---------------------------------------------------------------


@pytest.mark.django_db
def test_a_failed_job_keeps_its_error_message(world):
    job = queue.enqueue(world["submission"], Job.Kind.GRADING)
    queue.claim("worker-1")
    job.refresh_from_db()

    queue.finish(job, error="RuntimeError: no network")

    job.refresh_from_db()
    assert job.state == Job.State.FAILED
    assert "no network" in job.error
    assert job.finished_at is not None


@pytest.mark.django_db
def test_a_broken_job_does_not_stop_the_queue(world, calls, build_answer):
    """The next student is still waiting, so one failure must not block the rest."""

    def boom(*args, **kwargs):
        raise RuntimeError("the endpoint is gone")

    calls["raise_instead"](boom)

    queue.enqueue(world["submission"], Job.Kind.GRADING)

    from submissions import jobs

    job = queue.claim("worker-1")

    try:
        jobs.run(job)
    except Exception as error:
        queue.finish(job, error=str(error))

    job.refresh_from_db()
    # run_grading swallows the engine error itself and marks the submission.
    world["submission"].refresh_from_db()
    assert world["submission"].state == Submission.State.FAILED
    assert queue.claim("worker-1") is None


# --- what the student is told -----------------------------------------------


@pytest.mark.django_db
def test_the_status_endpoint_reports_the_place_in_the_queue(client, world, calls):
    client.force_login(world["student"])
    client.post(world["url"])

    answer = client.get(status_url(world)).json()

    assert answer["waiting"] is True
    assert answer["kind"] == Job.Kind.GRADING
    assert answer["position"] == 1
    assert answer["wait_seconds"] > 0
    assert answer["next_url"] == ""


@pytest.mark.django_db
def test_the_status_endpoint_sends_the_student_on_when_the_work_is_done(client, world, calls, work_queue):
    client.force_login(world["student"])
    client.post(world["url"])
    work_queue()

    answer = client.get(status_url(world)).json()

    assert answer["waiting"] is False
    assert answer["state"] == Submission.State.GRADED
    assert answer["next_url"] == world["url"]


@pytest.mark.django_db
def test_a_failed_evaluation_also_sends_the_student_to_the_result_page(
    client, world, calls, work_queue, build_answer
):
    """The result page is what explains the failure and offers the way back."""
    calls["answer"]["value"] = build_answer(pont=None)
    client.force_login(world["student"])
    client.post(world["url"])
    work_queue()

    answer = client.get(status_url(world)).json()

    assert answer["waiting"] is False
    assert answer["state"] == Submission.State.FAILED
    assert answer["next_url"] == world["url"]


@pytest.mark.django_db
def test_the_status_endpoint_never_answers_about_another_student(client, world, make_student):
    """It is the student's own place in the queue, not a view of the class."""
    intruder = make_student("intruder@example.com")
    Member.objects.create(user=intruder, group=world["group"])
    client.force_login(intruder)

    assert client.get(status_url(world)).status_code == 404


@pytest.mark.django_db
def test_the_status_endpoint_requires_login(client, world):
    assert client.get(status_url(world)).status_code in (302, 403)


# --- the waiting page -------------------------------------------------------


@pytest.mark.django_db
def test_the_recognition_page_shows_the_queue_while_waiting(client, world, calls):
    client.force_login(world["student"])
    client.post(world["url"])

    page = client.get(
        reverse(
            "ocr_recognition",
            kwargs={"group_id": world["group"].id, "lesson_id": world["lesson"].id},
        )
    )
    text = page.content.decode()

    assert page.context["queued"]["position"] == 1
    assert 'id="grading-content" hidden' in text
    assert "in the queue" in text or "your turn" in text


# --- recognition goes through the same queue --------------------------------


def recognition_url(world):
    return reverse(
        "ocr_recognition",
        kwargs={"group_id": world["group"].id, "lesson_id": world["lesson"].id},
    )


@pytest.mark.django_db
def test_recognition_is_queued_too(client, world, calls):
    """Recognition is the other long model call, so it waits in the same line."""
    client.force_login(world["student"])

    client.post(recognition_url(world))

    job = Job.objects.get(submission=world["submission"], kind=Job.Kind.OCR)
    assert job.state == Job.State.QUEUED

    world["submission"].refresh_from_db()
    assert world["submission"].state == Submission.State.OCR_RUNNING
    assert world["submission"].ocr_in_progress is True


@pytest.mark.django_db
def test_recognition_cannot_be_queued_twice(client, world, calls):
    """The reservation on the submission is what stops the second run."""
    client.force_login(world["student"])

    client.post(recognition_url(world))
    client.post(recognition_url(world))

    assert Job.objects.filter(submission=world["submission"], kind=Job.Kind.OCR).count() == 1


@pytest.mark.django_db
def test_the_three_run_limit_still_holds(client, world, calls):
    """The limit is counted on the submission, not on the queue."""
    Submission.objects.filter(pk=world["submission"].pk).update(ocr_run_count=3)
    client.force_login(world["student"])

    client.post(recognition_url(world))

    assert Job.objects.filter(kind=Job.Kind.OCR).count() == 0


# --- the worker command -----------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_the_worker_command_empties_the_queue(client, world, calls):
    """End to end: the view queues, run_worker does the work, the result lands."""
    from django.core.management import call_command

    client.force_login(world["student"])
    client.post(world["url"])

    call_command("run_worker", "--once", "--workers", "1", "--interval", "0.01")

    job = Job.objects.get(submission=world["submission"])
    assert job.state == Job.State.DONE
    assert job.finished_at is not None
    assert job.duration_seconds is not None

    world["submission"].refresh_from_db()
    assert world["submission"].state == Submission.State.GRADED
    assert Evaluation.objects.filter(submission=world["submission"]).count() == 1
