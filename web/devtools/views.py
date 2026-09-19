from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from .models import ProbaFuttatas


@staff_member_required
def proba(request):
    """Értékelés próbája OCR nélkül. (A form és a motor bekötése a következő lépés.)"""
    utolsok = ProbaFuttatas.objects.all()[:20]
    return render(request, "devtools/proba.html", {"utolsok": utolsok})
