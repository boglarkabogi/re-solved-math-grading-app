"""A lecke sorszáma, a határideje, és hogy az időpontok tényleg kapukat nyitnak."""

from datetime import datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from courses.models import Class, Group, Member
from courses.services import sync_lesson_states
from submissions.models import Assignment


def lesson_url(world):
    return reverse(
        "lesson_detail",
        kwargs={"group_id": world["group"].id, "lesson_id": world["lesson"].id},
    )


def generate_url(world):
    return reverse(
        "generate_assignment",
        kwargs={"group_id": world["group"].id, "lesson_id": world["lesson"].id},
    )


def recognition_url(world):
    return reverse(
        "ocr_recognition",
        kwargs={"group_id": world["group"].id, "lesson_id": world["lesson"].id},
    )


def at(lesson, state, opened=None, closed=None):
    """Beállítja az óra állapotát és időpontjait, órában mérve a mostanitól."""
    lesson.state = state
    lesson.opened_at = None if opened is None else timezone.now() + timedelta(hours=opened)
    lesson.closed_at = None if closed is None else timezone.now() + timedelta(hours=closed)
    lesson.save(update_fields=["state", "opened_at", "closed_at"])
    return lesson


# --- a sorszám --------------------------------------------------------------


@pytest.mark.django_db
def test_a_new_lesson_gets_the_next_number_in_its_group(world):
    second = Class.objects.create(group=world["group"], topic=world["lesson"].topic)
    third = Class.objects.create(group=world["group"], topic=world["lesson"].topic)

    assert world["lesson"].position == 1
    assert second.position == 2
    assert third.position == 3


@pytest.mark.django_db
def test_the_numbers_do_not_shift_when_an_earlier_lesson_is_deleted(world):
    """This is the bug: the old code counted positions, so deleting one lesson
    renamed every lesson after it."""
    second = Class.objects.create(group=world["group"], topic=world["lesson"].topic)
    third = Class.objects.create(group=world["group"], topic=world["lesson"].topic)

    second.delete()

    third.refresh_from_db()
    assert third.position == 3


@pytest.mark.django_db
def test_each_group_is_numbered_on_its_own(world):
    other = Group.objects.create(
        course=world["group"].course,
        name="2. csoport",
        invite_code="MASIKKOD",
    )

    assert Class.objects.create(group=other, topic=world["lesson"].topic).position == 1


# --- a származtatott állapot ------------------------------------------------


@pytest.mark.django_db
def test_a_planned_lesson_whose_time_has_come_counts_as_open(world):
    at(world["lesson"], Class.State.PLANNED, opened=-1, closed=1)

    assert world["lesson"].effective_state == Class.State.OPEN
    assert world["lesson"].is_open is True


@pytest.mark.django_db
def test_a_planned_lesson_with_both_times_in_the_past_counts_as_closed(world):
    """The teacher left it on "tervezett", but the window is over."""
    at(world["lesson"], Class.State.PLANNED, opened=-3, closed=-1)

    assert world["lesson"].effective_state == Class.State.CLOSED
    assert world["lesson"].is_open is False


@pytest.mark.django_db
def test_a_lesson_scheduled_for_later_counts_as_planned(world):
    at(world["lesson"], Class.State.OPEN, opened=2, closed=3)

    assert world["lesson"].effective_state == Class.State.PLANNED
    assert world["lesson"].is_open is False


@pytest.mark.django_db
def test_without_times_the_stored_state_decides(world):
    at(world["lesson"], Class.State.OPEN)
    assert world["lesson"].is_open is True

    at(world["lesson"], Class.State.PLANNED)
    assert world["lesson"].is_open is False


@pytest.mark.django_db
def test_the_stored_state_follows_the_times_in_both_directions(world):
    at(world["lesson"], Class.State.PLANNED, opened=-1, closed=1)
    assert sync_lesson_states()["opened"] == 1
    world["lesson"].refresh_from_db()
    assert world["lesson"].state == Class.State.OPEN

    at(world["lesson"], Class.State.OPEN, opened=-3, closed=-1)
    assert sync_lesson_states()["closed"] == 1
    world["lesson"].refresh_from_db()
    assert world["lesson"].state == Class.State.CLOSED


# --- amit a diák tapasztal --------------------------------------------------


@pytest.mark.django_db
def test_no_new_task_can_be_drawn_after_closing(client, world, make_student):
    newcomer = make_student("keso@example.com")
    Member.objects.create(user=newcomer, group=world["group"])
    at(world["lesson"], Class.State.OPEN, opened=-3, closed=-1)
    client.force_login(newcomer)

    answer = client.post(generate_url(world), follow=True)

    assert Assignment.objects.filter(student=newcomer).count() == 0
    messages = [str(m) for m in answer.context["messages"]]
    assert any("closed" in m for m in messages), messages
    assert answer.redirect_chain[-1][0] == lesson_url(world)


@pytest.mark.django_db
def test_no_task_can_be_drawn_before_the_lesson_starts(client, world, make_student):
    """The opening time was settable in the admin, but nothing enforced it."""
    newcomer = make_student("korai@example.com")
    Member.objects.create(user=newcomer, group=world["group"])
    at(world["lesson"], Class.State.OPEN, opened=2)
    client.force_login(newcomer)

    answer = client.post(generate_url(world), follow=True)

    assert Assignment.objects.filter(student=newcomer).count() == 0
    messages = [str(m) for m in answer.context["messages"]]
    assert any("has not started" in m for m in messages), messages


@pytest.mark.django_db
def test_a_student_who_already_started_still_reaches_their_work(client, world):
    """Closing must not lock out the students it was opened for."""
    at(world["lesson"], Class.State.OPEN, opened=-3, closed=-1)
    client.force_login(world["student"])

    answer = client.get(lesson_url(world))

    assert answer.status_code == 302
    assert "recognition" in answer.url or "evaluation" in answer.url


# --- a határidő a lapon -----------------------------------------------------


@pytest.mark.django_db
def test_the_page_shows_the_closing_time_as_the_deadline(client, world):
    world["lesson"].closed_at = timezone.make_aware(datetime(2026, 11, 23, 10, 35))
    world["lesson"].save(update_fields=["closed_at"])
    client.force_login(world["student"])

    text = client.get(recognition_url(world)).content.decode()

    assert "2026.11.23. 10:35" in text


@pytest.mark.django_db
def test_the_page_leaves_the_deadline_out_when_there_is_none(client, world):
    """A lesson with no closing time must not show an empty "Due to:" label."""
    world["lesson"].closed_at = None
    world["lesson"].save(update_fields=["closed_at"])
    client.force_login(world["student"])

    text = client.get(recognition_url(world)).content.decode()

    assert "Due to" not in text
