from django.conf import settings
from django.db import models


class Kurzus(models.Model):
    nev = models.CharField("név", max_length=120)
    felev = models.CharField("félév", max_length=20)  # pl. 2026/27/1
    moodle_kurzus_id = models.CharField("Moodle kurzus-azonosító", max_length=64, blank=True)

    class Meta:
        verbose_name = "kurzus"
        verbose_name_plural = "kurzusok"

    def __str__(self):
        return f"{self.nev} ({self.felev})"


class Csoport(models.Model):
    kurzus = models.ForeignKey(Kurzus, on_delete=models.CASCADE, related_name="csoportok")
    nev = models.CharField("név", max_length=120)
    meghivokod = models.CharField("meghívókód", max_length=16, unique=True)
    moodle_csoport_id = models.CharField("Moodle csoport-azonosító", max_length=64, blank=True)

    class Meta:
        verbose_name = "csoport"
        verbose_name_plural = "csoportok"

    def __str__(self):
        return f"{self.kurzus.nev} – {self.nev}"


class Tagsag(models.Model):
    felhasznalo = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tagsagok"
    )
    csoport = models.ForeignKey(Csoport, on_delete=models.CASCADE, related_name="tagsagok")
    oktato = models.BooleanField("oktató a csoportban", default=False)
    csatlakozott = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("felhasznalo", "csoport")]
        verbose_name = "csoporttagság"
        verbose_name_plural = "csoporttagságok"

    def __str__(self):
        return f"{self.felhasznalo} – {self.csoport}"


class Ora(models.Model):
    """Egy órai alkalom: a tanár kézzel nyitja és zárja."""

    class Allapot(models.TextChoices):
        TERVEZETT = "tervezett", "tervezett"
        NYITOTT = "nyitott", "nyitott"
        LEZART = "lezart", "lezárt"

    csoport = models.ForeignKey(Csoport, on_delete=models.CASCADE, related_name="orak")
    nev = models.CharField("név", max_length=120, blank=True)
    allapot = models.CharField("állapot", max_length=16, choices=Allapot.choices, default=Allapot.TERVEZETT)
    nyitva_ekkor = models.DateTimeField("megnyitva", null=True, blank=True)
    zarva_ekkor = models.DateTimeField("lezárva", null=True, blank=True)
    pontba_szamit = models.BooleanField("pontba számít", default=True)
    letrehozva = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "óra"
        verbose_name_plural = "órák"

    def __str__(self):
        return f"{self.csoport} – {self.nev or self.letrehozva.date()}"

    @property
    def nyitott(self):
        return self.allapot == self.Allapot.NYITOTT


class GyakorlasEngedely(models.Model):
    csoport = models.ForeignKey(Csoport, on_delete=models.CASCADE, related_name="gyakorlas_engedelyek")
    temakor = models.ForeignKey("bank.Topic", on_delete=models.CASCADE)
    napi_limit = models.PositiveIntegerField("napi limit", default=20)

    class Meta:
        unique_together = [("csoport", "temakor")]
        verbose_name = "gyakorlási engedély"
        verbose_name_plural = "gyakorlási engedélyek"

    def __str__(self):
        return f"{self.csoport} – {self.temakor}"
