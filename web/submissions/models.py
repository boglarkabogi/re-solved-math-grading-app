import uuid
from pathlib import Path

from django.conf import settings
from django.db import models


def image_path(instance, filename):
    extension = Path(filename).suffix.lower()

    return f"submissions/{instance.submission.public_id}/{uuid.uuid4().hex}{extension}"


class Assignment(models.Model):
    """Egy konkrét feladat egy konkrét diáknak."""

    class Mode(models.TextChoices):
        CLASS = "orai", "órai"
        PRACTICE = "gyakorlo", "gyakorló"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assignments"
    )
    task = models.ForeignKey("bank.TaskBank", on_delete=models.PROTECT, related_name="assignments")
    session = models.ForeignKey(
        "courses.Class", null=True, blank=True, on_delete=models.CASCADE, related_name="assignments"
    )
    mode = models.CharField("mode", max_length=16, choices=Mode.choices, default=Mode.CLASS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "kiosztás"
        verbose_name_plural = "kiosztások"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "session"],
                condition=models.Q(mode="orai"),
                name="one_class_task_per_student",
            ),
        ]

    def __str__(self):
        return f"{self.student} – {self.task.code}"


class Submission(models.Model):
    class State(models.TextChoices):
        ASSIGNED = "kiosztva", "kiosztva"
        IMAGE_UPLOADED = "kep_feltoltve", "kép feltöltve"
        OCR_RUNNING = "ocr_fut", "felismerés folyamatban"
        OCR_DONE = "ocr_kesz", "felismerés kész"
        GRADING = "ertekeles_fut", "értékelés folyamatban"
        GRADED = "ertekelve", "értékelve"
        FAILED = "hiba", "hiba"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    assignment = models.OneToOneField(Assignment, on_delete=models.CASCADE, related_name="submission")
    state = models.CharField("állapot", max_length=20, choices=State.choices, default=State.ASSIGNED)
    student_note = models.TextField("a diák megjegyzése", blank=True)
    approved_at = models.DateTimeField("jóváhagyva", null=True, blank=True)
    needs_review = models.BooleanField("tanári ellenőrzést igényel", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    ocr_run_count = models.PositiveSmallIntegerField(default=0)
    ocr_in_progress = models.BooleanField(default=False)

    class Meta:
        verbose_name = "beadás"
        verbose_name_plural = "beadások"

    def __str__(self):
        return f"{self.assignment} – {self.get_state_display()}"


class OcrAttempt(models.Model):
    """Minden feltöltött kép és a belőle felismert szöveg megmarad."""

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="ocr_attempts")
    image = models.ImageField("kép", upload_to=image_path)
    ocr_text = models.TextField("felismert szöveg", blank=True)
    model_name = models.CharField("modell", max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "felismerési kísérlet"
        verbose_name_plural = "felismerési kísérletek"

    def __str__(self):
        return f"{self.submission.public_id} – {self.created_at:%Y.%m.%d. %H:%M}"


class Evaluation(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="evaluations")
    model_name = models.CharField("modell", max_length=120)
    score = models.DecimalField("modell pontja", max_digits=3, decimal_places=2, null=True)
    reasoning = models.TextField("indoklás", blank=True)
    confidence = models.PositiveSmallIntegerField("magabiztosság", null=True, blank=True)
    ocr_error_suspected = models.BooleanField("OCR-hiba gyanúja", default=False)
    ocr_error_reason = models.TextField("az OCR-hiba gyanújának indoka", blank=True)
    student_final_answer = models.CharField("a diák végeredménye", max_length=255, blank=True)
    raw_response = models.TextField("a modell nyers válasza", blank=True)
    prompt = models.TextField("az elküldött prompt", blank=True)

    teacher_score = models.DecimalField("tanári pont", max_digits=3, decimal_places=2, null=True, blank=True)
    teacher_note = models.TextField("a felülbírálás indoka", blank=True)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="teacher_overrides",
    )
    teacher_scored_at = models.DateTimeField(null=True, blank=True)
    student_feedback = models.TextField("a diák visszajelzése", blank=True)
    student_feedback_at = models.DateTimeField(null=True, blank=True)
    moodle_synced_at = models.DateTimeField(null=True, blank=True)
    moodle_resend = models.BooleanField("újraküldendő a Moodle-be", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "értékelés"
        verbose_name_plural = "értékelések"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.submission} – {self.final_score} pont"

    @property
    def final_score(self):
        """A tanári pont az erősebb; ha nincs, a modellé."""
        return self.teacher_score if self.teacher_score is not None else self.score

class Job(models.Model):
    """One queued piece of model work: a recognition run or an evaluation run.

    The calls to the OCR and the grading model take tens of seconds, so they
    cannot run inside the request: a classroom of students pressing the button
    at the same time would tie up every web worker and run into the provider's
    rate limit. The view only writes a row here, and a separate worker process
    picks the rows up in the order they arrived.

    The finished rows are also the measurement data: when a run was queued,
    when it started, how long it took and whether it failed.
    """

    class Kind(models.TextChoices):
        OCR = "ocr", "felismerés"
        GRADING = "ertekeles", "értékelés"

    class State(models.TextChoices):
        QUEUED = "sorban", "sorban áll"
        RUNNING = "fut", "fut"
        DONE = "kesz", "kész"
        FAILED = "hiba", "hiba"

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="jobs")
    kind = models.CharField("fajta", max_length=16, choices=Kind.choices)
    state = models.CharField("állapot", max_length=16, choices=State.choices, default=State.QUEUED)

    queued_at = models.DateTimeField("sorba került", auto_now_add=True)
    started_at = models.DateTimeField("elindult", null=True, blank=True)
    finished_at = models.DateTimeField("befejeződött", null=True, blank=True)

    attempts = models.PositiveSmallIntegerField("próbálkozások", default=0)
    error = models.TextField("hiba", blank=True)
    worker = models.CharField("feldolgozó", max_length=80, blank=True)

    class Meta:
        # A sor sorrendje: ami előbb került be, az megy előbb.
        ordering = ["queued_at", "id"]
        indexes = [
            # A feldolgozó minden körben ezt kérdezi le, ezért kap saját indexet.
            models.Index(fields=["state", "queued_at"], name="job_state_queued_idx"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} – {self.submission_id} – {self.get_state_display()}"

    @property
    def duration_seconds(self):
        """How long the run took, or None while it has not finished."""
        if self.started_at is None or self.finished_at is None:
            return None

        return (self.finished_at - self.started_at).total_seconds()

    @property
    def waited_seconds(self):
        """How long the student waited in the queue before the run started."""
        if self.started_at is None:
            return None

        return (self.started_at - self.queued_at).total_seconds()
