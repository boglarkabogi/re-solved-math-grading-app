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
    expected_score = models.DecimalField("elvárt pont", max_digits=3, decimal_places=2, null=True, blank=True)
    confidence = models.PositiveSmallIntegerField("magabiztosság", null=True, blank=True)
    duration_ms = models.PositiveIntegerField("futásidő (ms)", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "próbafuttatás"
        verbose_name_plural = "próbafuttatások"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y.%m.%d. %H:%M} – {self.model_name} – {self.score}"

    @property
    def matches_expected(self):
        if self.score is None or self.expected_score is None:
            return None

        return self.score == self.expected_score


class BenchmarkCase(models.Model):
    """One item of the regression set: the score this solution should get."""

    label = models.CharField("címke", max_length=120, blank=True)
    task_code = models.CharField("feladat kódja", max_length=64, blank=True)
    topic = models.ForeignKey(
        "bank.Topic",
        verbose_name="témakör",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="benchmark_cases",
    )
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
    system_prompt = models.TextField("a futtatáshoz használt prompt", blank=True)
    case_count = models.PositiveIntegerField("esetek száma", default=0)
    match_count = models.PositiveIntegerField("egyezések száma", default=0)
    mean_deviation = models.FloatField("átlagos eltérés", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "regressziós futás"
        verbose_name_plural = "regressziós futások"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y.%m.%d. %H:%M} – {self.model_name} ({self.match_count}/{self.case_count})"

    @property
    def topic_summary(self):
        """A futásban szereplő témakör, vagy 'vegyes', ha több is van."""
        labels = sorted(
            {label for label in self.results.values_list("topic_label", flat=True) if label}
        )

        if not labels:
            return "–"

        if len(labels) == 1:
            return labels[0]

        return f"vegyes ({len(labels)})"


class BenchmarkResult(models.Model):
    """What one model said about one case in one run."""

    run = models.ForeignKey(BenchmarkRun, on_delete=models.CASCADE, related_name="results")
    case_label = models.CharField("teszteset neve", max_length=120, blank=True)
    topic_label = models.CharField("témakör", max_length=120, blank=True)
    case = models.ForeignKey(
        BenchmarkCase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="results",
    )
    expected_score = models.DecimalField("elvárt pont", max_digits=3, decimal_places=2)
    score = models.DecimalField("kapott pont", max_digits=3, decimal_places=2, null=True, blank=True)
    reasoning = models.TextField("indoklás", blank=True)
    confidence = models.PositiveSmallIntegerField("magabiztosság", null=True, blank=True)
    raw_response = models.TextField("nyers válasz", blank=True)
    error = models.TextField("hiba", blank=True)
    duration_ms = models.PositiveIntegerField("futásidő (ms)", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "teszteset eredménye"
        verbose_name_plural = "tesztesetek eredményei"
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(fields=["run", "case"], name="one_result_per_case_per_run"),
        ]

    def __str__(self):
        return f"{self.case_label or self.case} – kapott: {self.score}"

    @property
    def deviation(self):
        """How far the model landed from the score a human would give."""
        if self.score is None:
            return None

        return abs(self.score - self.expected_score)

    @property
    def matches(self):
        return self.score is not None and self.score == self.expected_score
