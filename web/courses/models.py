from django.conf import settings
from django.db import models


class Course(models.Model):
    name = models.CharField("név", max_length=120)
    term = models.CharField("félév", max_length=20)  # pl. 2026/27/1
    moodle_course_id = models.CharField("Moodle kurzus-azonosító", max_length=64, blank=True)

    class Meta:
        verbose_name = "kurzus"
        verbose_name_plural = "kurzusok"

    def __str__(self):
        return f"{self.name} ({self.term})"


class Group(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="csoportok")
    name = models.CharField("név", max_length=120)
    invite_code = models.CharField("meghívókód", max_length=16, unique=True)
    moodle_group_id = models.CharField("Moodle csoport-azonosító", max_length=64, blank=True)

    class Meta:
        verbose_name = "csoport"
        verbose_name_plural = "csoportok"

    def __str__(self):
        return f"{self.course.name} – {self.name}"


class Member(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tagsagok")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="tagsagok")
    is_teacher = models.BooleanField("oktató a csoportban", default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "group")]
        verbose_name = "csoporttagság"
        verbose_name_plural = "csoporttagságok"

    def __str__(self):
        return f"{self.user} – {self.group}"


class Class(models.Model):
    """Egy órai alkalom: a tanár kézzel nyitja és zárja."""

    class State(models.TextChoices):
        PLANNED = "tervezett", "tervezett"
        OPEN = "nyitott", "nyitott"
        CLOSED = "lezart", "lezárt"

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="orak")
    name = models.CharField("név", max_length=120, blank=True)
    state = models.CharField("állapot", max_length=16, choices=State.choices, default=State.PLANNED)
    opened_at = models.DateTimeField("megnyitva", null=True, blank=True)
    closed_at = models.DateTimeField("lezárva", null=True, blank=True)
    counts_towards_grade = models.BooleanField("pontba számít", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "óra"
        verbose_name_plural = "órák"

    def __str__(self):
        return f"{self.group} – {self.name or self.created_at.date()}"

    @property
    def is_open(self):
        return self.state == self.State.OPEN


class PracticePermission(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="practice_permissions")
    topic = models.ForeignKey("bank.Topic", on_delete=models.CASCADE)
    daily_limit = models.PositiveIntegerField("napi limit", default=20)

    class Meta:
        unique_together = [("group", "topic")]
        verbose_name = "gyakorlási engedély"
        verbose_name_plural = "gyakorlási engedélyek"

    def __str__(self):
        return f"{self.group} – {self.topic}"
