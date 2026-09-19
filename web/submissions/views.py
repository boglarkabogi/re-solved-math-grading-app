from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Beadas


@login_required
def sajat_beadasok(request):
    beadasok = (Beadas.objects
                .filter(kiosztas__diak=request.user)
                .select_related("kiosztas__feladat")
                .order_by("-letrehozva"))
    return render(request, "submissions/sajat_beadasok.html", {"beadasok": beadasok})
