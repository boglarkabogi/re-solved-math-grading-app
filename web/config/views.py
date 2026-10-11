from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def home(request):
    return render(request, "home.html")


@login_required
def generated_assignment(request):
    attempt = int(request.GET.get("attempt", 1))

    return render(
        request,
        "generated_assignment.html",
        {
            "attempt": attempt,
        },
    )


@login_required
def ocr_recognition(request):
    attempt = int(request.GET.get("attempt", 1))

    # 1 és 3 között tartjuk
    attempt = max(1, min(attempt, 3))

    return render(
        request,
        "ocr_recognition.html",
        {
            "attempt": attempt,
        },
    )


@login_required
def evaluation(request):
    attempt = int(request.GET.get("attempt", 1))
    attempt = max(1, min(attempt, 3))

    return render(
        request,
        "evaluation.html",
        {
            "attempt": attempt,
        },
    )
