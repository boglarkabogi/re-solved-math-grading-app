import time
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from bank.models import TaskBank
from motor.grading import grade
from motor.parsing import extract_json

from .csv_import import CsvError, read_cases
from .forms import BenchmarkCsvForm, BenchmarkRunForm, TrialRunForm
from .models import BenchmarkCase, BenchmarkResult, BenchmarkRun, TrialRun


@staff_member_required
def trial_run(request):
    if request.method == "POST":
        form = TrialRunForm(request.POST)
        if not form.is_valid():
            return render(request, "devtools/_result.html", {"form_errors": form.errors}, status=400)
        return _run(request, form.cleaned_data)
    return render(request, "devtools/trial_run.html", _page_context(request))


def _page_context(request):
    return {
        "form": TrialRunForm(initial=_initial_from_task_bank(request)),
        "csv_form": BenchmarkCsvForm(),
        "benchmark_form": BenchmarkRunForm(),
        "recent_runs": TrialRun.objects.all()[:20],
        "bank_tasks": TaskBank.objects.filter(active=True).select_related("topic").order_by("code"),
        "cases": BenchmarkCase.objects.all(),
        "benchmark_runs": BenchmarkRun.objects.all()[:10],
    }


@staff_member_required
def trial_run_detail(request, run_id):
    """Show a stored trial run again, in the place a fresh one appears.

    The saved columns are the truth; the raw answer only fills in the fields
    the table never had a column for, like the student's final answer.
    """
    run = get_object_or_404(TrialRun, pk=run_id)

    result = extract_json(run.raw_response) or {}
    result.update(
        {
            "pont": run.score,
            "indoklas": run.reasoning,
            "magabiztossag": run.confidence,
        }
    )

    error = None

    if run.score is None:
        error = "Ennél a futtatásnál nem született pont. A nyers válasz lent megnézhető."

    return render(
        request,
        "devtools/_result.html",
        {
            "result": result,
            "run": run,
            "error": error,
            "expected_score": None,
            "stored": True,
        },
    )


def _initial_from_task_bank(request):
    """?task=<id> prefills the task and the reference solution from the bank."""
    task_id = request.GET.get("task")
    if not task_id:
        return {}
    task = TaskBank.objects.filter(pk=task_id).first()
    if task is None:
        return {}
    return {
        "task_text": task.task_text,
        "correct_solution": task.correct_solution,
        "label": task.code,
    }


def _run(request, data):
    started = time.monotonic()
    result, call_error = None, None
    try:
        result = grade(
            data["task_text"],
            data["correct_solution"],
            data["solution_text"],
            diak_megjegyzes=data.get("student_note") or None,
            modell=data.get("model_name") or None,
        )
    except Exception as error:
        # On the developer page a failure is information, not a crash: show it.
        call_error = f"{type(error).__name__}: {error}"
    duration_ms = int((time.monotonic() - started) * 1000)

    result = result or {}
    score = result.get("pont")
    run = TrialRun.objects.create(
        run_by=request.user,
        task_text=data["task_text"],
        correct_solution=data["correct_solution"],
        solution_text=data["solution_text"],
        model_name=result.get("modell") or data.get("model_name") or "",
        prompt=result.get("prompt") or "",
        raw_response=result.get("nyers_valasz") or "",
        score=score,
        reasoning=result.get("indoklas") or "",
        confidence=result.get("magabiztossag"),
        duration_ms=duration_ms,
    )

    expected = data.get("expected_score")
    benchmark_case = None
    if score is not None and data.get("save_as_benchmark_case"):
        benchmark_case = BenchmarkCase.objects.create(
            label=data.get("label") or f"eset-{run.pk}",
            task_text=data["task_text"],
            correct_solution=data["correct_solution"],
            solution_text=data["solution_text"],
            expected_score=expected,
        )

    return render(
        request,
        "devtools/_result.html",
        {
            "result": result,
            # the engine reports a bad JSON response in 'hiba'; the call itself may also fail
            "error": call_error or result.get("hiba"),
            "run": run,
            "expected_score": expected,
            "matches_expected": expected is not None and score is not None and float(expected) == score,
            "benchmark_case": benchmark_case,
        },
    )


@staff_member_required
@require_POST
def import_cases(request):
    """Load benchmark cases from an uploaded CSV."""
    form = BenchmarkCsvForm(request.POST, request.FILES)

    if not form.is_valid():
        messages.error(request, "Nem sikerült beolvasni a fájlt.")
        return redirect("devtools:trial-run")

    try:
        rows = read_cases(form.cleaned_data["csv_file"].read())
    except CsvError as error:
        messages.error(request, str(error))
        return redirect("devtools:trial-run")

    if form.cleaned_data.get("replace_existing"):
        removed, _ = BenchmarkCase.objects.all().delete()
        messages.info(request, f"{removed} korábbi sor törölve.")

    BenchmarkCase.objects.bulk_create(BenchmarkCase(**row) for row in rows)

    messages.success(request, f"{len(rows)} teszteset betöltve.")

    return redirect("devtools:trial-run")


@staff_member_required
@require_POST
def benchmark_start(request):
    """Open a run. The page then asks for one case at a time."""
    form = BenchmarkRunForm(request.POST)
    form.is_valid()

    case_count = BenchmarkCase.objects.count()

    if case_count == 0:
        return render(request, "devtools/_benchmark.html", {"empty": True})

    run = BenchmarkRun.objects.create(
        model_name=form.cleaned_data.get("model_name") or "",
        prompt_version=form.cleaned_data.get("prompt_version") or "",
        case_count=case_count,
    )

    return render(request, "devtools/_benchmark.html", _benchmark_context(run))


@staff_member_required
def benchmark_step(request, run_id):
    """Grade the next case that has no result in this run yet.

    One case per request on purpose: a model call takes seconds, and a set of
    thirty would sit in a single request for minutes. This way every result
    shows up as it arrives and the run can be abandoned by closing the page.
    """
    run = get_object_or_404(BenchmarkRun, pk=run_id)

    case = BenchmarkCase.objects.exclude(results__run=run).order_by("pk").first()

    if case is not None:
        _grade_case(run, case)
        _update_totals(run)

    return render(request, "devtools/_benchmark.html", _benchmark_context(run))


def _grade_case(run, case):
    started = time.monotonic()
    result, call_error = None, None

    try:
        result = grade(
            case.task_text, case.correct_solution, case.solution_text, modell=run.model_name or None
        )
    except Exception as error:
        # One broken case must not stop the run: record it and move on.
        call_error = f"{type(error).__name__}: {error}"

    result = result or {}
    score = result.get("pont")

    BenchmarkResult.objects.create(
        run=run,
        case=case,
        expected_score=case.expected_score,
        score=Decimal(str(score)) if score is not None else None,
        reasoning=result.get("indoklas") or "",
        confidence=result.get("magabiztossag"),
        raw_response=result.get("nyers_valasz") or "",
        error=call_error or result.get("hiba") or "",
        duration_ms=int((time.monotonic() - started) * 1000),
    )

    if not run.model_name and result.get("modell"):
        run.model_name = result["modell"]
        run.save(update_fields=["model_name"])


def _update_totals(run):
    results = run.results.all()
    scored = [result for result in results if result.score is not None]

    run.match_count = sum(1 for result in scored if result.matches)
    run.mean_deviation = float(sum(result.deviation for result in scored) / len(scored)) if scored else None
    run.save(update_fields=["match_count", "mean_deviation"])


def _benchmark_context(run):
    results = run.results.select_related("case").order_by("case_id")
    done = results.count()

    return {
        "run": run,
        "results": results,
        "done": done,
        "remaining": max(run.case_count - done, 0),
        "average_ms": results.aggregate(value=Avg("duration_ms"))["value"],
    }
