from django.conf import settings
from django.db import models


class TrialRun(models.Model):
    """One grading run from the developer page, skipping the recognition step."""

    run_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    task_text = models.TextField("feladat")
    correct_solution = models.TextField("helyes megoldás")
    solution_text = models.TextField("a kiértékelt megoldás")
    model_name = models.CharField("modell", max_length=120, blank=True)
    prompt = models.TextField("az elküldött prompt", blank=True)
    raw_response = models.TextField("nyers válasz", blank=True)
    score = models.DecimalField("pont", max_digits=3, decimal_places=2, null=True, blank=True)
    reasoning = models.TextField("indoklás", blank=True)
    confidence = models.PositiveSmallIntegerField("magabiztosság", null=True, blank=True)
    duration_ms = models.PositiveIntegerField("futásidő (ms)", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "próbafuttatás"
        verbose_name_plural = "próbafuttatások"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y.%m.%d. %H:%M} – {self.model_name} – {self.score}"


class BenchmarkCase(models.Model):
    """One item of the regression set: the score this solution should get."""

    label = models.CharField("címke", max_length=120, blank=True)
    task_text = models.TextField("feladat")
    correct_solution = models.TextField("helyes megoldás")
    solution_text = models.TextField("a diák megoldása")
    expected_score = models.DecimalField("elvárt pont", max_digits=3, decimal_places=2)
    comment = models.TextField("megjegyzés", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "teszteset"
        verbose_name_plural = "tesztesetek"
        ordering = ["pk"]

    def __str__(self):
        return f"{self.label or 'teszteset'} (elvárt: {self.expected_score})"


class BenchmarkRun(models.Model):
    """Running the whole regression set with one model."""

    model_name = models.CharField("modell", max_length=120)
    prompt_version = models.CharField("prompt verziója", max_length=40, blank=True)
    case_count = models.PositiveIntegerField("esetek száma", default=0)
    match_count = models.PositiveIntegerField("egyezések száma", default=0)
    mean_deviation = models.FloatField("átlagos eltérés", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "regressziós futás"
        verbose_name_plural = "regressziós futások"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.created_at:%Y.%m.%d. %H:%M} – {self.model_name} "
            f"({self.match_count}/{self.case_count})"
        )
