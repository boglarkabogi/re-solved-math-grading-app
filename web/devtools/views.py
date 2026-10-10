from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from .models import TrialRun


@staff_member_required
def trial_run(request):
    """Grading trial without the recognition step. (Form and engine come next.)"""
    recent_runs = TrialRun.objects.all()[:20]
    return render(request, "devtools/trial_run.html", {"recent_runs": recent_runs})
