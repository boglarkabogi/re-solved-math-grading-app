"""A lesson names its topic, instead of the topic being guessed from its name.

Before this the task drawing matched Class.name against Topic.name, so a lesson
called "LNKO" found nothing while the topic was "Legnagyobb közös osztó" - and
the student only learnt that in the middle of the class.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from bank.models import TaskBank, Topic
from courses.models import Class, Course, Group, Member
from submissions.models import Assignment


@pytest.fixture
def lesson(db):
    topic = Topic.objects.create(code="lnko", name="Legnagyobb közös osztó")
    TaskBank.objects.create(
        topic=topic,
        code="lnko-1",
        task_text="Mennyi lnko(12, 18)?",
        correct_solution="6",
        use=TaskBank.Use.CLASS,
    )
    course = Course.objects.create(name="Dimat I.", term="2026/27/1")
    group = Group.objects.create(course=course, name="1. csoport", invite_code="ABC123")

    # A short name that matches no topic name at all: this used to break it.
    return Class.objects.create(group=group, topic=topic, name="LNKO", state=Class.State.OPEN)


@pytest.fixture
def student(lesson):
    user = get_user_model().objects.create_user(username="s", email="s@example.com", password="x")
    Member.objects.create(user=user, group=lesson.group)
    return user


# --- what the page shows ----------------------------------------------------


@pytest.mark.django_db
def test_the_short_name_is_shown_when_there_is_one(lesson):
    assert lesson.display_name == "LNKO"


@pytest.mark.django_db
def test_without_a_short_name_the_topic_is_shown(lesson):
    lesson.name = ""

    assert lesson.display_name == "Legnagyobb közös osztó"


@pytest.mark.django_db
def test_a_lesson_without_a_topic_still_has_something_to_show(lesson):
    lesson.name = ""
    lesson.topic = None

    assert lesson.display_name  # the date, rather than an empty heading


# --- drawing a task ---------------------------------------------------------


def generate_url(lesson):
    return reverse(
        "generate_assignment",
        kwargs={"group_id": lesson.group_id, "lesson_id": lesson.id},
    )


@pytest.mark.django_db
def test_a_task_is_drawn_from_the_topic_not_from_the_name(client, lesson, student):
    client.force_login(student)

    client.post(generate_url(lesson))

    assignment = Assignment.objects.get(student=student, session=lesson)
    assert assignment.task.topic == lesson.topic


@pytest.mark.django_db
def test_a_lesson_without_a_topic_says_so(client, lesson, student):
    lesson.topic = None
    lesson.save(update_fields=["topic"])
    client.force_login(student)

    answer = client.post(generate_url(lesson), follow=True)

    assert Assignment.objects.count() == 0
    assert any("no topic set" in str(message) for message in answer.context["messages"])
