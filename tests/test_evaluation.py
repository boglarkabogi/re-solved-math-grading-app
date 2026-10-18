"""Tests for the evaluation step: ownership, comment saving, guards."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from bank.models import TaskBank, Topic
from courses.models import Class, Course, Group, Member
from submissions.models import Assignment, Evaluation, OcrAttempt, Submission


def make_student(email):
    return get_user_model().objects.create_user(username=email.split("@")[0], email=email, password="x")


@pytest.fixture
def world(db):
    topic = Topic.objects.create(code="lnko", name="LNKO")
    task = TaskBank.objects.create(
        topic=topic, code="lnko-1", task_text="Mennyi lnko(12, 18)?", correct_solution="6"
    )
    course = Course.objects.create(name="Dimat I.", term="2026/27/1")
    group = Group.objects.create(course=course, name="1. csoport", invite_code="ABC123")
    lesson = Class.objects.create(group=group, name="LNKO")

    student = make_student("s@example.com")
    Member.objects.create(user=student, group=group)

    assignment = Assignment.objects.create(student=student, task=task, session=lesson)
    submission = Submission.objects.create(assignment=assignment, state=Submission.State.OCR_DONE)
    OcrAttempt.objects.create(submission=submission, ocr_text="12 = 2*6, 18 = 3*6, lnko = 6", ocr_run_count=1)
    return {
        "student": student,
        "group": group,
        "lesson": lesson,
        "submission": submission,
        "task": task,
    }


def url_for(world):
    return reverse(
        "evaluation",
        kwargs={"group_id": world["group"].id, "lesson_id": world["lesson"].id},
    )


@pytest.mark.django_db
def test_page_requires_login(client, world):
    assert client.get(url_for(world)).status_code in (302, 403)


@pytest.mark.django_db
def test_the_view_hands_the_task_and_the_recognised_text_to_the_template(client, world):
    """We assert on the context, not on the markup: the template may change."""
    client.force_login(world["student"])

    answer = client.get(url_for(world))

    assert answer.status_code == 200
    assert answer.context["assignment"].task.task_text == "Mennyi lnko(12, 18)?"
    assert answer.context["ocr_attempt"].ocr_text == "12 = 2*6, 18 = 3*6, lnko = 6"
    assert answer.context["evaluation"] is None
    assert answer.context["lesson_number"] == 1


@pytest.mark.django_db
def test_posting_saves_the_student_note(client, world):
    client.force_login(world["student"])

    answer = client.post(
        url_for(world),
        {"student_note": "a 3. sorban 144 van, nem 134"},
    )

    assert answer.status_code == 302  # redirect to the GET view
    world["submission"].refresh_from_db()
    assert world["submission"].student_note == "a 3. sorban 144 van, nem 134"


@pytest.mark.django_db
def test_the_saved_note_is_handed_back_to_the_template(client, world):
    client.force_login(world["student"])
    client.post(url_for(world), {"student_note": "  elgépelés a 2. sorban  "})

    answer = client.get(url_for(world))

    # whitespace is trimmed on save
    assert answer.context["submission"].student_note == "elgépelés a 2. sorban"


@pytest.mark.django_db
def test_another_students_submission_is_not_reachable(client, world):
    intruder = make_student("intruder@example.com")
    Member.objects.create(user=intruder, group=world["group"])
    client.force_login(intruder)

    answer = client.get(url_for(world))

    assert answer.status_code == 404


@pytest.mark.django_db
def test_a_non_member_is_sent_home(client, world):
    outsider = make_student("outsider@example.com")
    client.force_login(outsider)

    answer = client.get(url_for(world))

    assert answer.status_code == 302
    assert answer.url == reverse("home")


@pytest.mark.django_db
def test_without_recognised_text_it_sends_back_to_recognition(client, world):
    world["submission"].ocr_attempts.update(ocr_text="")
    client.force_login(world["student"])

    answer = client.get(url_for(world))

    assert answer.status_code == 302
    assert "recognition" in answer.url


@pytest.mark.django_db
def test_an_existing_evaluation_is_shown(client, world):
    Evaluation.objects.create(
        submission=world["submission"],
        model_name="teszt/modell",
        score="0.75",
        reasoning="Jó módszer, apró hiba.",
    )
    client.force_login(world["student"])

    answer = client.get(url_for(world))

    result = answer.context["evaluation"]
    assert float(result.score) == 0.75
    assert result.reasoning == "Jó módszer, apró hiba."


@pytest.mark.django_db
def test_a_post_without_the_field_keeps_the_earlier_note(client, world):
    """The evaluation page can restart grading without showing the comment box."""
    client.force_login(world["student"])
    client.post(url_for(world), {"student_note": "fontos megjegyzés"})

    client.post(url_for(world), {})  # no student_note field at all

    world["submission"].refresh_from_db()
    assert world["submission"].student_note == "fontos megjegyzés"
