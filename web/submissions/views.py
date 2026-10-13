from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Submission


@login_required
def my_submissions(request):
    submissions = (
        Submission.objects.filter(assignment__student=request.user)
        .select_related("assignment__task")
        .order_by("-created_at")
    )
    return render(request, "submissions/my_submissions.html", {"submissions": submissions})
