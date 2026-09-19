from django.conf import settings
from django.db import models


class ProbaFuttatas(models.Model):
    """Egy kiértékelés a fejlesztői felületről, az OCR-lépés kihagyásával."""

    futtatta = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    feladat_szoveg = models.TextField("feladat")
    helyes_megoldas = models.TextField("helyes megoldás")
    megoldas_szoveg = models.TextField("a kiértékelt megoldás")
    hibatipus = models.CharField("generált hibatípus", max_length=32, blank=True)
    modell = models.CharField("modell", max_length=120, blank=True)
    prompt = models.TextField("az elküldött prompt", blank=True)
    nyers_valasz = models.TextField("nyers válasz", blank=True)
    pont = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    indoklas = models.TextField(blank=True)
    magabiztossag = models.PositiveSmallIntegerField(null=True, blank=True)
    futasido_ms = models.PositiveIntegerField(null=True, blank=True)
    letrehozva = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "próbafuttatás"
        verbose_name_plural = "próbafuttatások"
        ordering = ["-letrehozva"]

    def __str__(self):
        return f"{self.letrehozva:%Y.%m.%d. %H:%M} – {self.modell} – {self.pont}"


class Teszteset(models.Model):
    """A regressziós készlet egy eleme: mire mennyi pont járna."""

    cimke = models.CharField("címke", max_length=120, blank=True)
    feladat_szoveg = models.TextField("feladat")
    helyes_megoldas = models.TextField("helyes megoldás")
    megoldas_szoveg = models.TextField("a diák megoldása")
    elvart_pont = models.DecimalField("elvárt pont", max_digits=3, decimal_places=2)
    megjegyzes = models.TextField(blank=True)
    letrehozva = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "teszteset"
        verbose_name_plural = "tesztesetek"

    def __str__(self):
        return f"{self.cimke or 'teszteset'} (elvárt: {self.elvart_pont})"


class RegressziosFutas(models.Model):
    """A teljes tesztkészlet végigfuttatása egy modellel."""

    modell = models.CharField(max_length=120)
    prompt_verzio = models.CharField(max_length=40, blank=True)
    esetek_szama = models.PositiveIntegerField(default=0)
    egyezes = models.PositiveIntegerField(default=0)
    atlagos_elteres = models.FloatField(null=True, blank=True)
    letrehozva = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "regressziós futás"
        verbose_name_plural = "regressziós futások"
        ordering = ["-letrehozva"]

    def __str__(self):
        return f"{self.letrehozva:%Y.%m.%d. %H:%M} – {self.modell} ({self.egyezes}/{self.esetek_szama})"
