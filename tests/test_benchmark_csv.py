"""Loading a regression set from CSV and running it case by case."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from bank.models import TaskBank, Topic
from devtools import views as devtools_views
from devtools.csv_import import CsvError, read_cases
from devtools.models import BenchmarkCase, BenchmarkResult, BenchmarkRun

HEADER = "label,task_text,correct_solution,solution_text,expected_score,comment\n"


@pytest.fixture
def staff(db):
    return get_user_model().objects.create_user(
        username="dev", email="dev@example.com", password="x", is_staff=True
    )


def upload(text, name="cases.csv"):
    return SimpleUploadedFile(name, text.encode("utf-8"), content_type="text/csv")


# --- reading the file -------------------------------------------------------


@pytest.mark.django_db
def test_a_plain_file_is_read():
    rows = read_cases((HEADER + "lnko-1,Mennyi lnko(12/18)?,6,12 = 2*6,1,ok\n").encode("utf-8"))

    assert len(rows) == 1
    assert rows[0]["label"] == "lnko-1"
    assert rows[0]["expected_score"] == Decimal("1")


@pytest.mark.django_db
def test_hungarian_headers_semicolons_and_a_bom_are_survived():
    """This is what a spreadsheet export looks like on a Hungarian Windows."""
    text = "﻿cimke;feladat;helyes_megoldas;megoldas;elvart_pont\nA;f;m;sz;0,75\n"

    rows = read_cases(text.encode("utf-8"))

    assert rows[0]["expected_score"] == Decimal("0.75")


@pytest.mark.django_db
def test_a_row_may_name_a_task_from_the_bank():
    topic = Topic.objects.create(code="lnko", name="LNKO")
    TaskBank.objects.create(
        topic=topic, code="lnko-7", task_text="Mennyi lnko(213, 200)?", correct_solution="1"
    )

    rows = read_cases(b"task_code,solution_text,expected_score\nlnko-7,213 = 1*200 + 13,0.5\n")

    assert rows[0]["task_text"] == "Mennyi lnko(213, 200)?"
    assert rows[0]["correct_solution"] == "1"


@pytest.mark.django_db
def test_an_unknown_task_code_is_named_in_the_error():
    with pytest.raises(CsvError, match="nincs-ilyen"):
        read_cases(b"task_code,solution_text,expected_score\nnincs-ilyen,sz,1\n")


@pytest.mark.django_db
def test_a_score_off_the_scale_is_refused():
    with pytest.raises(CsvError, match="elvárt pont csak"):
        read_cases((HEADER + "A,f,m,sz,0.6,\n").encode("utf-8"))


@pytest.mark.django_db
def test_a_missing_column_is_explained():
    with pytest.raises(CsvError, match="hiányzik"):
        read_cases(b"label,task_text\nA,f\n")


# --- the import view --------------------------------------------------------


@pytest.mark.django_db
def test_the_import_creates_the_cases(client, staff):
    client.force_login(staff)

    client.post(
        reverse("devtools:import-cases"),
        {"csv_file": upload(HEADER + "A,f,m,sz,1,\nB,f2,m2,sz2,0,\n")},
    )

    assert BenchmarkCase.objects.count() == 2


@pytest.mark.django_db
def test_the_import_can_replace_the_earlier_set(client, staff):
    BenchmarkCase.objects.create(
        label="regi", task_text="f", correct_solution="m", solution_text="sz", expected_score="1"
    )
    client.force_login(staff)

    client.post(
        reverse("devtools:import-cases"),
        {"csv_file": upload(HEADER + "uj,f,m,sz,1,\n"), "replace_existing": "on"},
    )

    assert [case.label for case in BenchmarkCase.objects.all()] == ["uj"]


@pytest.mark.django_db
def test_a_broken_file_changes_nothing(client, staff):
    client.force_login(staff)

    client.post(reverse("devtools:import-cases"), {"csv_file": upload("label\nA\n")})

    assert BenchmarkCase.objects.count() == 0


@pytest.mark.django_db
def test_the_page_is_closed_to_students(client):
    student = get_user_model().objects.create_user(username="s", email="s@example.com", password="x")
    client.force_login(student)

    answer = client.post(reverse("devtools:import-cases"), {"csv_file": upload(HEADER)})

    assert answer.status_code in (302, 403)
    assert BenchmarkCase.objects.count() == 0


# --- running the set --------------------------------------------------------


@pytest.fixture
def two_cases(db):
    for label, expected in (("egy", "1"), ("ketto", "0.5")):
        BenchmarkCase.objects.create(
            label=label,
            task_text="Mennyi lnko(12, 18)?",
            correct_solution="6",
            solution_text="12 = 2*6",
            expected_score=expected,
        )


@pytest.fixture
def engine(monkeypatch):
    """Stub the engine where devtools imported it, not where it is defined."""
    answers = {"value": {"pont": 1, "indoklas": "jo", "magabiztossag": 90, "modell": "teszt/modell"}}

    monkeypatch.setattr(devtools_views, "grade", lambda *args, **kwargs: answers["value"])

    return answers


@pytest.mark.django_db
def test_a_run_grades_one_case_per_request(client, staff, two_cases, engine):
    client.force_login(staff)

    client.post(reverse("devtools:benchmark-start"), {})

    run = BenchmarkRun.objects.get()
    assert run.case_count == 2
    assert run.results.count() == 0  # starting only opens the run

    client.get(reverse("devtools:benchmark-step", args=[run.pk]))
    assert run.results.count() == 1

    client.get(reverse("devtools:benchmark-step", args=[run.pk]))
    assert run.results.count() == 2

    # Nothing left to do, and no duplicate rows.
    client.get(reverse("devtools:benchmark-step", args=[run.pk]))
    assert run.results.count() == 2


@pytest.mark.django_db
def test_the_run_counts_the_matches_and_the_deviation(client, staff, two_cases, engine):
    client.force_login(staff)
    client.post(reverse("devtools:benchmark-start"), {})
    run = BenchmarkRun.objects.get()

    for _step in range(2):
        client.get(reverse("devtools:benchmark-step", args=[run.pk]))

    run.refresh_from_db()

    # The engine always answers 1: it matches the first case, misses the second by 0.5.
    assert run.match_count == 1
    assert run.mean_deviation == pytest.approx(0.25)


@pytest.mark.django_db
def test_a_broken_case_is_recorded_and_the_run_goes_on(client, staff, two_cases, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("no network")

    monkeypatch.setattr(devtools_views, "grade", boom)
    client.force_login(staff)
    client.post(reverse("devtools:benchmark-start"), {})
    run = BenchmarkRun.objects.get()

    for _step in range(2):
        client.get(reverse("devtools:benchmark-step", args=[run.pk]))

    assert run.results.count() == 2
    assert all(result.score is None for result in run.results.all())
    assert "no network" in BenchmarkResult.objects.first().error


@pytest.mark.django_db
def test_starting_without_cases_says_so(client, staff, engine):
    client.force_login(staff)

    answer = client.post(reverse("devtools:benchmark-start"), {})

    assert b"Nincs egyetlen teszteset" in answer.content
    assert BenchmarkRun.objects.count() == 0
