"""Tests for wiring the grading engine into the evaluation step.

grade() is replaced everywhere, so no test ever calls a model endpoint.
"""

import pytest

from submissions.models import Evaluation, Submission


@pytest.mark.django_db
def test_a_post_runs_the_engine_and_stores_the_result(client, world, calls):
    client.force_login(world["student"])

    client.post(world["url"])

    assert len(calls["recorded"]) == 1

    evaluation = Evaluation.objects.get(submission=world["submission"])
    assert str(evaluation.score) == "0.75"
    assert evaluation.reasoning == "Jó módszer, apró hiba."
    assert evaluation.confidence == 80
    assert evaluation.model_name == "teszt/modell"
    assert evaluation.student_final_answer == "6"
    assert evaluation.raw_response == '{"pont": 0.75}'
    assert evaluation.prompt == "SYSTEM\n\n---\n\nUSER"


@pytest.mark.django_db
def test_no_personal_data_is_handed_to_the_engine(client, world, calls):
    """The engine may only see the task, the solution, the text and the note."""
    student = world["student"]
    student.first_name = "Tímea"
    student.last_name = "Kovácsné-Szabó"
    student.email = "timea.kovacsne@example.com"
    student.save()

    client.force_login(student)

    client.post(world["url"], {"student_note": "a 2. sorban 7 van"})

    args, kwargs = calls["recorded"][0]
    everything_sent = " ".join(str(value) for value in list(args) + list(kwargs.values()))

    assert "Mennyi lnko(12, 18)?" in everything_sent
    assert "12 = 2*6" in everything_sent
    assert "a 2. sorban 7 van" in everything_sent

    for personal in (student.first_name, student.last_name, student.email):
        assert personal not in everything_sent


@pytest.mark.django_db
def test_a_successful_evaluation_moves_the_submission_to_graded(client, world, calls):
    client.force_login(world["student"])

    client.post(world["url"])

    world["submission"].refresh_from_db()
    assert world["submission"].state == Submission.State.GRADED
    assert world["submission"].needs_review is False


@pytest.mark.django_db
def test_a_graded_submission_cannot_be_evaluated_again(client, world, calls):
    client.force_login(world["student"])
    client.post(world["url"])

    client.post(world["url"])

    assert len(calls["recorded"]) == 1
    assert Evaluation.objects.filter(submission=world["submission"]).count() == 1


@pytest.mark.django_db
def test_a_missing_score_fails_the_submission_but_keeps_the_answer(client, world, calls, build_answer):
    calls["answer"]["value"] = build_answer(pont=None, hiba="A modell nem adott JSON választ.")
    client.force_login(world["student"])

    client.post(world["url"])

    world["submission"].refresh_from_db()
    assert world["submission"].state == Submission.State.FAILED
    assert world["submission"].needs_review is True

    evaluation = Evaluation.objects.get(submission=world["submission"])
    assert evaluation.score is None
    assert evaluation.raw_response == '{"pont": 0.75}'


@pytest.mark.django_db
def test_a_failed_submission_may_be_retried(client, world, calls, build_answer):
    calls["answer"]["value"] = build_answer(pont=None)
    client.force_login(world["student"])
    client.post(world["url"])

    calls["answer"]["value"] = build_answer()
    client.post(world["url"])

    world["submission"].refresh_from_db()
    assert world["submission"].state == Submission.State.GRADED
    assert len(calls["recorded"]) == 2


@pytest.mark.django_db
def test_a_crashing_engine_does_not_lose_the_submission(client, world, calls):
    def boom(*args, **kwargs):
        raise RuntimeError("no network")

    calls["raise_instead"](boom)
    client.force_login(world["student"])

    response = client.post(world["url"])

    assert response.status_code == 302
    world["submission"].refresh_from_db()
    assert world["submission"].state == Submission.State.FAILED
    assert world["submission"].needs_review is True
    assert Evaluation.objects.filter(submission=world["submission"]).count() == 0


@pytest.mark.django_db
def test_a_suspected_recognition_error_asks_for_a_teacher(client, world, calls, build_answer):
    calls["answer"]["value"] = build_answer(ocr_hiba_gyanu=True)
    client.force_login(world["student"])

    client.post(world["url"])

    world["submission"].refresh_from_db()
    assert world["submission"].state == Submission.State.GRADED
    assert world["submission"].needs_review is True

    evaluation = Evaluation.objects.get(submission=world["submission"])
    assert evaluation.ocr_error_suspected is True


@pytest.mark.django_db
def test_a_score_outside_the_range_is_refused(client, world, calls, build_answer):
    calls["answer"]["value"] = build_answer(pont=7)
    client.force_login(world["student"])

    client.post(world["url"])

    evaluation = Evaluation.objects.get(submission=world["submission"])
    assert evaluation.score is None
    world["submission"].refresh_from_db()
    assert world["submission"].state == Submission.State.FAILED


@pytest.mark.django_db
def test_an_unusable_confidence_is_stored_as_empty(client, world, calls, build_answer):
    calls["answer"]["value"] = build_answer(magabiztossag="nagyon")
    client.force_login(world["student"])

    client.post(world["url"])

    evaluation = Evaluation.objects.get(submission=world["submission"])
    assert evaluation.confidence is None


@pytest.mark.django_db
def test_the_result_is_shown_on_the_page_after_grading(client, world, calls):
    client.force_login(world["student"])
    client.post(world["url"])

    page = client.get(world["url"])

    assert page.context["evaluation"].reasoning == "Jó módszer, apró hiba."


@pytest.mark.django_db
def test_an_unreadable_text_is_flagged_for_the_teacher(client, world, calls, build_answer):
    """The model says it could not read the text: re-OCR, do not blame the student."""
    calls["answer"]["value"] = build_answer(
        pont=0,
        ertelmezheto=False,
        ocr_hiba_gyanu=True,
        ocr_hiba_indok="A sorok között nincs matematikailag értelmes lépés.",
    )
    client.force_login(world["student"])

    client.post(world["url"])

    evaluation = Evaluation.objects.get(submission=world["submission"])
    assert evaluation.ocr_error_suspected is True
    assert evaluation.ocr_error_reason.startswith("A sorok között")

    world["submission"].refresh_from_db()
    assert world["submission"].needs_review is True


@pytest.mark.django_db
def test_an_unreadable_text_is_flagged_even_without_the_ocr_field(client, world, calls, build_answer):
    calls["answer"]["value"] = build_answer(ertelmezheto=False, ocr_hiba_gyanu=False)
    client.force_login(world["student"])

    client.post(world["url"])

    assert Evaluation.objects.get(submission=world["submission"]).ocr_error_suspected is True


@pytest.mark.django_db
def test_a_score_off_the_scale_is_snapped_and_flagged(client, world, calls, build_answer):
    """The prompt allows five scores. 0.8 means the model ignored it."""
    calls["answer"]["value"] = build_answer(pont=0.8)
    client.force_login(world["student"])

    client.post(world["url"])

    evaluation = Evaluation.objects.get(submission=world["submission"])
    assert str(evaluation.score) == "0.75"

    world["submission"].refresh_from_db()
    assert world["submission"].state == Submission.State.GRADED
    assert world["submission"].needs_review is True


@pytest.mark.django_db
def test_every_allowed_score_is_kept_as_it_is(client, world, calls, build_answer):
    for given, expected in (("0", "0.00"), ("0.25", "0.25"), ("0.5", "0.50"), ("1", "1.00")):
        Evaluation.objects.all().delete()
        world["submission"].state = Submission.State.OCR_DONE
        world["submission"].needs_review = False
        world["submission"].save(update_fields=["state", "needs_review"])

        calls["answer"]["value"] = build_answer(pont=given)
        client.force_login(world["student"])
        client.post(world["url"])

        evaluation = Evaluation.objects.get(submission=world["submission"])
        assert str(evaluation.score) == expected
        world["submission"].refresh_from_db()
        assert world["submission"].needs_review is False, given


@pytest.mark.django_db
def test_the_reference_solution_never_reaches_the_student_page(client, world, calls, build_answer):
    """grade() echoes helyes_megoldas back, and it is stored in raw_response.

    The page may show the reasoning and the score, never the right answer.
    """
    calls["answer"]["value"] = build_answer(
        helyes_megoldas="A TITKOS HELYES MEGOLDAS",
        nyers_valasz='{"helyes_megoldas": "A TITKOS HELYES MEGOLDAS", "pont": 0.75}',
    )
    client.force_login(world["student"])
    client.post(world["url"])

    page = client.get(world["url"])

    assert b"TITKOS" not in page.content
