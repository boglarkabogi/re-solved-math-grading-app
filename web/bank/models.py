from django.conf import settings
from django.db import models


class Topic(models.Model):
    code = models.SlugField("kód", unique=True)  # lnko, kongruencia, polinom_lnko
    name = models.CharField("név", max_length=120)

    class Meta:
        verbose_name = "témakör"
        verbose_name_plural = "témakörök"

    def __str__(self):
        return self.name


class TaskBank(models.Model):
    """Kézzel felvitt feladat. A helyes megoldás bekerül az értékelő promptba."""

    class Use(models.TextChoices):
        CLASS = "orai", "csak órai"
        PRACTICE = "gyakorlo", "csak gyakorló"
        BOTH = "mindketto", "mindkettő"

    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="feladatok")
    code = models.CharField("kód", max_length=64, unique=True)
    task_text = models.TextField("feladat szövege (Markdown + LaTeX)")
    correct_solution = models.TextField("helyes megoldás")
    difficulty = models.PositiveSmallIntegerField("nehézség", default=2)  # 1-3
    use = models.CharField(max_length=16, choices=Use.choices, default=Use.BOTH)
    active = models.BooleanField("aktív", default=True)
    comment = models.TextField("tanári megjegyzés", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "bankfeladat"
        verbose_name_plural = "bankfeladatok"
        ordering = ["topic", "code"]

    def __str__(self):
        return f"{self.code} ({self.topic})"
