"""A graded assignment is closed: the student sees the result, not the start.

Before these guards a student could walk back from the result, upload another
image, run the recognition again and ask for a second score.
"""

import pytest
from django.urls import reverse

from submissions.models import Submission


def step_urls(world):
    keys = {"group_id": world["group"].id, "lesson_id": world["lesson"].id}
    return {
        "lesson": reverse("lesson_detail", kwargs=keys),
        "assignment": reverse("generated_assignment", kwargs=keys),
        "recognition": reverse("ocr_recognition", kwargs=keys),
    }


def mark(submission, state):
    submission.state = state
    submission.save(update_fields=["state"])


@pytest.mark.django_db
@pytest.mark.parametrize("step", ["lesson", "assignment", "recognition"])
def test_a_graded_assignment_sends_every_step_to_the_result(client, world, step):
    mark(world["submission"], Submission.State.GRADED)
    client.force_login(world["student"])

    answer = client.get(step_urls(world)[step])

    assert answer.status_code == 302
    assert answer.url == world["url"]


@pytest.mark.django_db
def test_a_graded_assignment_cannot_start_another_recognition(client, world):
    mark(world["submission"], Submission.State.GRADED)
    client.force_login(world["student"])

    before = world["submission"].ocr_run_count

    answer = client.post(step_urls(world)["recognition"])

    assert answer.url == world["url"]

    world["submission"].refresh_from_db()
    assert world["submission"].ocr_run_count == before
    assert world["submission"].state == Submission.State.GRADED


@pytest.mark.django_db
def test_a_graded_assignment_cannot_take_another_image(client, world):
    mark(world["submission"], Submission.State.GRADED)
    client.force_login(world["student"])

    answer = client.post(step_urls(world)["assignment"], {"image": ""})

    assert answer.status_code == 302
    assert answer.url == world["url"]
    assert world["submission"].ocr_attempts.count() == 1


@pytest.mark.django_db
def test_the_lesson_page_leads_to_the_result_after_a_failed_grading(client, world):
    """A failed grading still belongs to the result page, where it can be retried."""
    mark(world["submission"], Submission.State.FAILED)
    client.force_login(world["student"])

    answer = client.get(step_urls(world)["lesson"])

    assert answer.status_code == 302
    assert answer.url == world["url"]


@pytest.mark.django_db
def test_a_failed_grading_still_allows_a_new_image(client, world):
    """FAILED means the engine broke, not that the student used up a try."""
    mark(world["submission"], Submission.State.FAILED)
    client.force_login(world["student"])

    answer = client.get(step_urls(world)["recognition"])

    assert answer.status_code == 200


@pytest.mark.django_db
def test_recognition_is_still_reachable_before_grading(client, world):
    """The guard must not block the normal flow."""
    client.force_login(world["student"])

    answer = client.get(step_urls(world)["recognition"])

    assert answer.status_code == 200
