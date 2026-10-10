"""Database-backed tests: basic model behaviour.

The `courses` models are still Hungarian (Kurzus, Csoport, Ora) because they
have not been renamed yet. When they are, only the imports and the attribute
names in the last test need to change.
"""

import pytest
from django.db import IntegrityError, transaction

from bank.models import TaskBank, Topic
from courses.models import Csoport, Kurzus, Ora


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
    assert task.difficulty == 2
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
    course = Kurzus.objects.create(nev="Dimat I.", felev="2026/27/1")
    group = Csoport.objects.create(kurzus=course, nev="1. csoport", meghivokod="ABC123")
    session = Ora.objects.create(csoport=group, nev="1. alkalom")

    assert session.nyitott is False

    session.allapot = Ora.Allapot.NYITOTT

    assert session.nyitott is True
