import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Diák, tanár vagy fejlesztő. A belépés e-mail-címmel és jelszóval történik."""

    class Role(models.TextChoices):
        STUDENT = "diak", "diák"
        TEACHER = "tanar", "tanár"
        DEVELOPER = "fejleszto", "fejlesztő"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField("e-mail-cím", unique=True)
    neptun_code = models.CharField("Neptun-kód", max_length=6, blank=True, db_index=True)
    role = models.CharField("szerep", max_length=16, choices=Role.choices, default=Role.STUDENT)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = "felhasználó"
        verbose_name_plural = "felhasználók"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.email})"


class ExternalId(models.Model):
    """Külső rendszerbeli azonosító (Moodle, ELTE-belépés) a felhasználóhoz kötve."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="external_ids")
    source = models.CharField("forrás", max_length=32)  # pl. "moodle-lti"
    issuer = models.CharField("kibocsátó", max_length=255, blank=True)
    external_id = models.CharField("külső azonosító", max_length=255)

    class Meta:
        unique_together = [("source", "issuer", "external_id")]
        verbose_name = "külső azonosító"
        verbose_name_plural = "külső azonosítók"

    def __str__(self):
        return f"{self.source}: {self.external_id}"
