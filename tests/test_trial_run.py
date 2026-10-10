"""Tests for the developer trial-run page. No real model call is made."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from motor import llm

GOOD_RESPONSE = json.dumps(
    {
        "feladat": "lnko(213, 200)",
        "helyes_megoldas": "1",
        "diak_vegeredmenye": "1",
        "diak_megoldasa_osszefoglalva": "Euklideszi algoritmus.",
        "pont": 1,
        "indoklas": "Helyes módszer, helyes végeredmény.",
        "magabiztossag": 92,
        "ertelmezheto": True,
        "ocr_hiba_gyanu": False,
        "ocr_hiba_indok": "",
    },
    ensure_ascii=False,
)


@pytest.fixture
def fake_model(monkeypatch):
    calls = []

    def chat(messages, modell=None, **kwargs):
        calls.append({"messages": messages, "model": modell})
        response = chat.response
        return response(messages) if callable(response) else response

    chat.response = GOOD_RESPONSE
    chat.calls = calls
    monkeypatch.setattr(llm, "chat", chat)
    return chat


@pytest.fixture
def staff(db):
    """A staff user. Works with both an email-only and a username-based manager."""
    user_model = get_user_model()
    try:
        return user_model.objects.create_user(email="dev@example.com", password="x", is_staff=True)
    except TypeError:
        return user_model.objects.create_user(
            username="dev", email="dev@example.com", password="x", is_staff=True
        )


@pytest.mark.django_db
def test_page_requires_login(client):
    assert client.get(reverse("devtools:trial-run")).status_code in (302, 403)


@pytest.mark.django_db
def test_page_renders_for_staff(client, staff):
    client.force_login(staff)
    answer = client.get(reverse("devtools:trial-run"))
    assert answer.status_code == 200
    assert "Értékelés próbája" in answer.content.decode()


@pytest.mark.django_db
def test_submitting_the_form_runs_the_grader(client, staff, fake_model):
    from devtools.models import TrialRun

    client.force_login(staff)
    answer = client.post(
        reverse("devtools:trial-run"),
        {
            "task_text": "lnko(213, 200)",
            "correct_solution": "1",
            "solution_text": "213 = 1*200 + 13 ... lnko = 1",
            "expected_score": "1",
        },
    )

    assert answer.status_code == 200
    assert "egyezik az elvárttal" in answer.content.decode()

    run = TrialRun.objects.get()
    assert float(run.score) == 1.0
    assert run.prompt
    assert run.raw_response == GOOD_RESPONSE
    assert run.duration_ms is not None
    assert run.run_by == staff


@pytest.mark.django_db
def test_student_note_reaches_the_prompt(client, staff, fake_model):
    client.force_login(staff)
    client.post(
        reverse("devtools:trial-run"),
        {
            "task_text": "t",
            "correct_solution": "r",
            "solution_text": "s",
            "student_note": "a 3. sorban 144 van, nem 134",
        },
    )
    assert "144" in fake_model.calls[-1]["messages"][-1]["content"]


@pytest.mark.django_db
def test_unparsable_response_is_shown_not_crashed(client, staff, fake_model):
    from devtools.models import TrialRun

    fake_model.response = "nincs itt JSON"
    client.force_login(staff)

    answer = client.post(
        reverse("devtools:trial-run"),
        {"task_text": "t", "correct_solution": "r", "solution_text": "s"},
    )

    assert answer.status_code == 200
    assert "Nem sikerült" in answer.content.decode()
    run = TrialRun.objects.get()
    assert run.score is None
    assert run.raw_response == "nincs itt JSON"


@pytest.mark.django_db
def test_network_failure_is_shown_not_crashed(client, staff, monkeypatch):
    def boom(messages, modell=None, **kwargs):
        raise RuntimeError("A modellhívás 3 próbálkozás után sem sikerült")

    monkeypatch.setattr(llm, "chat", boom)
    client.force_login(staff)

    answer = client.post(
        reverse("devtools:trial-run"),
        {"task_text": "t", "correct_solution": "r", "solution_text": "s"},
    )

    assert answer.status_code == 200
    assert "Nem sikerült" in answer.content.decode()


@pytest.mark.django_db
def test_saving_a_benchmark_case(client, staff, fake_model):
    from devtools.models import BenchmarkCase

    client.force_login(staff)
    client.post(
        reverse("devtools:trial-run"),
        {
            "task_text": "t",
            "correct_solution": "r",
            "solution_text": "s",
            "expected_score": "0.75",
            "label": "lnko-nagy-szamok",
            "save_as_benchmark_case": "on",
        },
    )

    case = BenchmarkCase.objects.get()
    assert case.label == "lnko-nagy-szamok"
    assert float(case.expected_score) == 0.75


@pytest.mark.django_db
def test_benchmark_case_needs_an_expected_score(client, staff, fake_model):
    from devtools.models import BenchmarkCase

    client.force_login(staff)
    answer = client.post(
        reverse("devtools:trial-run"),
        {
            "task_text": "t",
            "correct_solution": "r",
            "solution_text": "s",
            "save_as_benchmark_case": "on",
        },
    )

    assert answer.status_code == 400
    assert BenchmarkCase.objects.count() == 0


@pytest.mark.django_db
def test_prefill_from_the_task_bank(client, staff):
    from bank.models import TaskBank, Topic

    topic = Topic.objects.create(code="lnko", name="LNKO")
    TaskBank.objects.create(
        topic=topic, code="lnko-1", task_text="Mennyi lnko(12, 18)?", correct_solution="6"
    )
    client.force_login(staff)

    task = TaskBank.objects.get()
    answer = client.get(reverse("devtools:trial-run"), {"task": task.pk})

    body = answer.content.decode()
    assert "Mennyi lnko(12, 18)?" in body
