"""Shared test helpers."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from bank.models import TaskBank, Topic
from courses.models import Class, Course, Group, Member
from motor import llm
from submissions import services
from submissions.models import Assignment, OcrAttempt, Submission


def build_student(email):
    return get_user_model().objects.create_user(username=email.split("@")[0], email=email, password="x")


@pytest.fixture
def make_student():
    """Create an extra student inside a test (an intruder, an outsider)."""
    return build_student


@pytest.fixture
def world(db):
    topic = Topic.objects.create(code="lnko", name="LNKO")
    task = TaskBank.objects.create(
        topic=topic, code="lnko-1", task_text="Mennyi lnko(12, 18)?", correct_solution="6"
    )
    course = Course.objects.create(name="Dimat I.", term="2026/27/1")
    group = Group.objects.create(course=course, name="1. csoport", invite_code="ABC123")
    lesson = Class.objects.create(group=group, name="LNKO")

    student = build_student("s@example.com")
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
        "url": reverse("evaluation", kwargs={"group_id": group.id, "lesson_id": lesson.id}),
    }


@pytest.fixture(autouse=True)
def plain_static_files(settings):
    """Serve static files by plain path during tests.

    The project uses WhiteNoise's manifest storage, which looks every static
    file up in the manifest that `collectstatic` builds. In tests that manifest
    is either missing or out of date, so a template referring to a new CSS file
    would fail with "Missing staticfiles manifest entry" - a failure about the
    build, not about the code under test. Tests do not care about hashed file
    names, so here we fall back to the plain storage.
    """
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }


def answer(**overrides):
    """A grade() return value in the shape the system prompt asks for."""
    result = {
        "feladat": "Mennyi lnko(12, 18)?",
        "helyes_megoldas": "6",
        "diak_vegeredmenye": "6",
        "diak_megoldasa_osszefoglalva": "A diák felbontotta mindkét számot, és 6-ot kapott.",
        "pont": 0.75,
        "indoklas": "Jó módszer, apró hiba.",
        "magabiztossag": 80,
        "ertelmezheto": True,
        "ocr_hiba_gyanu": False,
        "ocr_hiba_indok": "",
        "pont_kerekitve": False,
        "nyers_valasz": '{"pont": 0.75}',
        "prompt": "SYSTEM\n\n---\n\nUSER",
        "modell": "teszt/modell",
    }
    result.update(overrides)
    return result


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Nothing in the test suite may talk to a model endpoint.

    The guard sits on llm.chat, the one door to the network, and not on
    grade(): a test that wants to exercise the real parsing and prompt
    building replaces llm.chat with its own stub, and that replacement wins
    over this one. If a test forgets to stub anything, it gets this error
    instead of a slow, billed call.
    """

    def refuse(*args, **kwargs):
        raise RuntimeError("A test tried to call a model. Stub llm.chat or use the `calls` fixture.")

    monkeypatch.setattr(llm, "chat", refuse)


@pytest.fixture
def calls(monkeypatch):
    """Replace the whole grading engine and record how it was called.

    For tests about what the app does with a result, not about how the
    result is produced.
    """
    recorded = []

    def fake_grade(*args, **kwargs):
        recorded.append((args, kwargs))
        return recorded_answer["value"]

    recorded_answer = {"value": answer()}
    monkeypatch.setattr(services.grading, "grade", fake_grade)

    def raise_instead(replacement):
        """Let a test make grade() blow up instead of answering."""
        monkeypatch.setattr(services.grading, "grade", replacement)

    return {"recorded": recorded, "answer": recorded_answer, "raise_instead": raise_instead}


@pytest.fixture
def build_answer():
    """Build a grade() answer with some fields overridden."""
    return answer
