from django.conf import settings
from django.db import models


class Temakor(models.Model):
    kod = models.SlugField("kód", unique=True)                       # lnko, kongruencia, polinom_lnko
    nev = models.CharField("név", max_length=120)
    prompt_kiegeszites = models.TextField("témakör-specifikus prompt", blank=True)

    class Meta:
        verbose_name = "témakör"
        verbose_name_plural = "témakörök"

    def __str__(self):
        return self.nev


class BankFeladat(models.Model):
    """Kézzel felvitt feladat. A helyes megoldás bekerül az értékelő promptba."""

    class Hasznalat(models.TextChoices):
        ORAI = "orai", "csak órai"
        GYAKORLO = "gyakorlo", "csak gyakorló"
        MINDKETTO = "mindketto", "mindkettő"

    temakor = models.ForeignKey(Temakor, on_delete=models.PROTECT, related_name="feladatok")
    kod = models.CharField("kód", max_length=64, unique=True)
    feladat_szoveg = models.TextField("feladat szövege (Markdown + LaTeX)")
    helyes_megoldas = models.TextField("helyes megoldás")
    nehezseg = models.PositiveSmallIntegerField("nehézség", default=2)   # 1-3
    hasznalat = models.CharField(max_length=16, choices=Hasznalat.choices, default=Hasznalat.MINDKETTO)
    aktiv = models.BooleanField("aktív", default=True)
    megjegyzes = models.TextField("tanári megjegyzés", blank=True)
    letrehozta = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="felvitt_feladatok")
    letrehozva = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "bankfeladat"
        verbose_name_plural = "bankfeladatok"
        ordering = ["temakor", "kod"]

    def __str__(self):
        return f"{self.kod} ({self.temakor})"
