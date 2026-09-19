"""A háttér-feldolgozó: sorban veszi a beadásokat, és lefuttatja a felismerést/értékelést.

Indítás:  python web/manage.py run_worker
"""
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from submissions.models import Beadas


class Command(BaseCommand):
    help = "A beadások feldolgozása (OCR + értékelés) sorban"

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=float, default=3.0, help="lekérdezés gyakorisága másodpercben")

    def handle(self, *args, **options):
        self.stdout.write("A feldolgozó elindult. Kilépés: Ctrl+C")
        while True:
            beadas = (Beadas.objects
                      .filter(allapot__in=[Beadas.Allapot.KEP_FELTOLTVE, Beadas.Allapot.ERTEKELES_FUT])
                      .order_by("letrehozva")
                      .first())
            if beadas is None:
                time.sleep(options["interval"])
                continue

            self.stdout.write(f"[{timezone.now():%H:%M:%S}] feldolgozás: {beadas.azonosito}")
            # TODO: motor.ocr.ocr_kep(...) és motor.grading.ertekel(...) bekötése
            time.sleep(options["interval"])
