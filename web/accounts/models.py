import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class Felhasznalo(AbstractUser):
    """Diák, tanár vagy fejlesztő. A belépés e-mail-címmel és jelszóval történik."""

    class Szerep(models.TextChoices):
        DIAK = "diak", "diák"
        TANAR = "tanar", "tanár"
        FEJLESZTO = "fejleszto", "fejlesztő"

    azonosito = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField("e-mail-cím", unique=True)
    neptun_kod = models.CharField("Neptun-kód", max_length=6, blank=True, db_index=True)
    szerep = models.CharField("szerep", max_length=16, choices=Szerep.choices, default=Szerep.DIAK)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = "felhasználó"
        verbose_name_plural = "felhasználók"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.email})"


class KulsoAzonosito(models.Model):
    """Külső rendszerbeli azonosító (Moodle, ELTE-belépés) a felhasználóhoz kötve."""

    felhasznalo = models.ForeignKey(Felhasznalo, on_delete=models.CASCADE, related_name="kulso_azonositok")
    forras = models.CharField("forrás", max_length=32)  # pl. "moodle-lti"
    issuer = models.CharField("kibocsátó", max_length=255, blank=True)
    kulso_id = models.CharField("külső azonosító", max_length=255)

    class Meta:
        unique_together = [("forras", "issuer", "kulso_id")]
        verbose_name = "külső azonosító"
        verbose_name_plural = "külső azonosítók"

    def __str__(self):
        return f"{self.forras}: {self.kulso_id}"
