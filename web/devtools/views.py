import time

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from bank.models import TaskBank
from motor.grading import grade
from .models import TrialRun, BenchmarkCase
from .forms import TrialRunForm


@staff_member_required
def trial_run(request):
    if request.method == "POST":
        form = TrialRunForm(request.POST)
        if not form.is_valid():
            return render(request, "devtools/_result.html", {"form_errors": form.errors}, status=400)
        return _run(request, form.cleaned_data)
    return render(
        request,
        "devtools/trial_run.html",
        {
            "form": TrialRunForm(initial=_initial_from_task_bank(request)),
            "recent_runs": TrialRun.objects.all()[:20],
            "bank_tasks": TaskBank.objects.filter(active=True).select_related("topic")[:50],
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