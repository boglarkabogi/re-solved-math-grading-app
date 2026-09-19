import uuid

from django.conf import settings
from django.db import models


def kep_utvonal(instance, filename):
    return f"beadasok/{instance.beadas.azonosito}/{uuid.uuid4().hex}.jpg"


class Kiosztas(models.Model):
    """Egy konkrét feladat egy konkrét diáknak."""

    class Mod(models.TextChoices):
        ORAI = "orai", "órai"
        GYAKORLO = "gyakorlo", "gyakorló"

    diak = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kiosztasok")
    feladat = models.ForeignKey("bank.BankFeladat", on_delete=models.PROTECT, related_name="kiosztasok")
    ora = models.ForeignKey("courses.Ora", null=True, blank=True, on_delete=models.CASCADE,
                            related_name="kiosztasok")
    mod = models.CharField("mód", max_length=16, choices=Mod.choices, default=Mod.ORAI)
    letrehozva = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "kiosztás"
        verbose_name_plural = "kiosztások"
        constraints = [
            models.UniqueConstraint(fields=["diak", "ora"], condition=models.Q(mod="orai"),
                                    name="egy_orai_feladat_diakonkent"),
        ]

    def __str__(self):
        return f"{self.diak} – {self.feladat.kod}"


class Beadas(models.Model):
    class Allapot(models.TextChoices):
        KIOSZTVA = "kiosztva", "kiosztva"
        KEP_FELTOLTVE = "kep_feltoltve", "kép feltöltve"
        OCR_FUT = "ocr_fut", "felismerés folyamatban"
        OCR_KESZ = "ocr_kesz", "felismerés kész"
        ERTEKELES_FUT = "ertekeles_fut", "értékelés folyamatban"
        ERTEKELVE = "ertekelve", "értékelve"
        HIBA = "hiba", "hiba"

    azonosito = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    kiosztas = models.OneToOneField(Kiosztas, on_delete=models.CASCADE, related_name="beadas")
    allapot = models.CharField("állapot", max_length=20, choices=Allapot.choices, default=Allapot.KIOSZTVA)
    diak_megjegyzes = models.TextField("a diák megjegyzése", blank=True)
    jovahagyva = models.DateTimeField("jóváhagyva", null=True, blank=True)
    ellenorizendo = models.BooleanField("tanári ellenőrzést igényel", default=False)
    letrehozva = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "beadás"
        verbose_name_plural = "beadások"

    def __str__(self):
        return f"{self.kiosztas} – {self.get_allapot_display()}"


class OcrKiserlet(models.Model):
    """Minden feltöltött kép és a belőle felismert szöveg megmarad."""

    beadas = models.ForeignKey(Beadas, on_delete=models.CASCADE, related_name="ocr_kiserletek")
    kep = models.ImageField("kép", upload_to=kep_utvonal)
    ocr_szoveg = models.TextField("felismert szöveg", blank=True)
    modell = models.CharField("modell", max_length=120, blank=True)
    letrehozva = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["letrehozva"]
        verbose_name = "felismerési kísérlet"
        verbose_name_plural = "felismerési kísérletek"


class Ertekeles(models.Model):
    beadas = models.ForeignKey(Beadas, on_delete=models.CASCADE, related_name="ertekelesek")
    modell = models.CharField("modell", max_length=120)
    pont = models.DecimalField("modell pontja", max_digits=3, decimal_places=2, null=True)
    indoklas = models.TextField("indoklás", blank=True)
    magabiztossag = models.PositiveSmallIntegerField("magabiztosság", null=True, blank=True)
    ocr_7_1_gyanu = models.BooleanField(default=False)
    ocr_hiba_gyanu = models.BooleanField(default=False)
    nyers_valasz = models.TextField("a modell nyers válasza", blank=True)
    prompt = models.TextField("az elküldött prompt", blank=True)

    tanari_pont = models.DecimalField("tanári pont", max_digits=3, decimal_places=2, null=True, blank=True)
    tanari_indok = models.TextField("a felülbírálás indoka", blank=True)
    tanari_pont_ki = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name="felulbiralasok")
    tanari_pont_mikor = models.DateTimeField(null=True, blank=True)

    moodle_atvezetve = models.DateTimeField(null=True, blank=True)
    ujrakuldendo = models.BooleanField("újraküldendő a Moodle-be", default=False)
    letrehozva = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "értékelés"
        verbose_name_plural = "értékelések"

    @property
    def vegleges_pont(self):
        """A tanári pont az erősebb; ha nincs, a modellé."""
        return self.tanari_pont if self.tanari_pont is not None else self.pont
