"""Database-backed tests: basic model behaviour."""

import pytest
from django.db import IntegrityError, transaction

from bank.models import TaskBank, Topic
from courses.models import Group, Course, Class


@pytest.mark.django_db
def test_task_is_created_with_the_expected_defaults():
    topic = Topic.objects.create(code="lnko", name="Legnagyobb közös osztó")

    task = TaskBank.objects.create(
        topic=topic,
        code="lnko-213-200",
        task_text="Mennyi lnko(213, 200)?",
        correct_solution="1",
    )

    assert task.active is True
    assert task.use == TaskBank.Use.BOTH
    assert "lnko-213-200" in str(task)


@pytest.mark.django_db
def test_task_code_must_be_unique():
    """Two tasks with the same code would break the repeatable CSV import."""
    topic = Topic.objects.create(code="lnko", name="Legnagyobb közös osztó")
    TaskBank.objects.create(topic=topic, code="dup", task_text="a", correct_solution="b")

    with pytest.raises(IntegrityError), transaction.atomic():
        TaskBank.objects.create(topic=topic, code="dup", task_text="c", correct_solution="d")


@pytest.mark.django_db
def test_topic_is_shown_by_its_name():
    topic = Topic.objects.create(code="kongruencia", name="Lineáris kongruencia")

    assert str(topic) == "Lineáris kongruencia"


@pytest.mark.django_db
def test_class_session_is_closed_until_it_is_opened():
    course = Course.objects.create(name="Diszkrét matematika I.", term="2026/27/1")
    group = Group.objects.create(course=course, name="1. csoport", invite_code="ABC123")
    session = Class.objects.create(group=group, name="1. alkalom")

    assert session.is_open is False

    session.state = Class.State.OPEN

    assert session.is_open is True
