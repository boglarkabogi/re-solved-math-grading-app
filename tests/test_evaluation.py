"""Tests for the evaluation step: ownership, comment saving, guards."""

import pytest
from django.urls import reverse

from courses.models import Member
from submissions.models import Evaluation, Submission


@pytest.mark.django_db
def test_page_requires_login(client, world):
    assert client.get(world["url"]).status_code in (302, 403)


@pytest.mark.django_db
def test_the_view_hands_the_task_and_the_recognised_text_to_the_template(client, world):
    """We assert on the context, not on the markup: the template may change."""
    client.force_login(world["student"])

    answer = client.get(world["url"])

    assert answer.status_code == 200
    assert answer.context["assignment"].task.task_text == "Mennyi lnko(12, 18)?"
    assert answer.context["ocr_attempt"].ocr_text == "12 = 2*6, 18 = 3*6, lnko = 6"
    assert answer.context["evaluation"] is None
    assert answer.context["lesson_number"] == 1


@pytest.mark.django_db
def test_posting_saves_the_student_note(client, world, calls):
    client.force_login(world["student"])

    answer = client.post(
        world["url"],
        {"student_note": "a 3. sorban 144 van, nem 134"},
    )

    assert answer.status_code == 302  # redirect to the GET view
    world["submission"].refresh_from_db()
    assert world["submission"].student_note == "a 3. sorban 144 van, nem 134"


@pytest.mark.django_db
def test_the_saved_note_is_handed_back_to_the_template(client, world, calls):
    client.force_login(world["student"])
    client.post(world["url"], {"student_note": "  elgépelés a 2. sorban  "})

    answer = client.get(world["url"])

    # whitespace is trimmed on save
    assert answer.context["submission"].student_note == "elgépelés a 2. sorban"


@pytest.mark.django_db
def test_another_students_submission_is_not_reachable(client, world, make_student):
    intruder = make_student("intruder@example.com")
    Member.objects.create(user=intruder, group=world["group"])
    client.force_login(intruder)

    answer = client.get(world["url"])

    assert answer.status_code == 404


@pytest.mark.django_db
def test_a_non_member_is_sent_home(client, world, make_student):
    outsider = make_student("outsider@example.com")
    client.force_login(outsider)

    answer = client.get(world["url"])

    assert answer.status_code == 302
    assert answer.url == reverse("home")


@pytest.mark.django_db
def test_without_recognised_text_it_sends_back_to_recognition(client, world):
    world["submission"].ocr_attempts.update(ocr_text="")
    client.force_login(world["student"])

    answer = client.get(world["url"])

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

    answer = client.get(world["url"])

    result = answer.context["evaluation"]
    assert float(result.score) == 0.75
    assert result.reasoning == "Jó módszer, apró hiba."


@pytest.mark.django_db
def test_a_post_without_the_field_keeps_the_earlier_note(client, world, calls):
    """The evaluation page can restart grading without showing the comment box."""
    client.force_login(world["student"])
    client.post(world["url"], {"student_note": "fontos megjegyzés"})

    client.post(world["url"], {})  # no student_note field at all

    world["submission"].refresh_from_db()
    assert world["submission"].student_note == "fontos megjegyzés"


# --- feedback to the teacher ------------------------------------------------


@pytest.fixture
def graded(world):
    """A submission that already has a finished evaluation."""
    world["submission"].state = Submission.State.GRADED
    world["submission"].save(update_fields=["state"])
    world["evaluation"] = Evaluation.objects.create(
        submission=world["submission"],
        model_name="teszt/modell",
        score="0.75",
        reasoning="Jó módszer, apró hiba.",
    )
    return world


@pytest.mark.django_db
def test_feedback_is_saved_and_flags_the_submission_for_review(client, graded):
    client.force_login(graded["student"])

    client.post(graded["url"], {"student_feedback": "  a 2. sorban 7 van, nem 1  "})

    graded["evaluation"].refresh_from_db()
    graded["submission"].refresh_from_db()
    assert graded["evaluation"].student_feedback == "a 2. sorban 7 van, nem 1"
    assert graded["evaluation"].student_feedback_at is not None
    assert graded["submission"].needs_review is True


@pytest.mark.django_db
def test_feedback_without_an_evaluation_changes_nothing(client, world):
    client.force_login(world["student"])

    client.post(world["url"], {"student_feedback": "nincs mire"})

    world["submission"].refresh_from_db()
    assert world["submission"].needs_review is False


@pytest.mark.django_db
def test_a_graded_submission_cannot_be_evaluated_again(client, graded, calls):
    client.force_login(graded["student"])

    answer = client.post(graded["url"], {}, follow=True)

    messages = [str(m) for m in answer.context["messages"]]
    assert "This submission has already been evaluated." in messages


@pytest.mark.django_db
def test_a_failed_submission_may_be_retried(client, world, calls):
    world["submission"].state = Submission.State.FAILED
    world["submission"].save(update_fields=["state"])
    client.force_login(world["student"])

    answer = client.post(world["url"], {}, follow=True)

    messages = [str(m) for m in answer.context["messages"]]
    assert "already been evaluated" not in " ".join(messages)


@pytest.mark.django_db
def test_sending_feedback_does_not_touch_the_score(client, graded):
    client.force_login(graded["student"])

    client.post(graded["url"], {"student_feedback": "nem értek egyet"})

    graded["evaluation"].refresh_from_db()
    assert float(graded["evaluation"].score) == 0.75
    assert graded["evaluation"].teacher_score is None
