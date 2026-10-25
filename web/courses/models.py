import secrets

from django.conf import settings
from django.db import models

INVITE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
INVITE_CODE_LENGTH = 6


def generate_invite_code(length=INVITE_CODE_LENGTH):
    """A fresh invite code that no group uses yet."""

    from django.apps import apps

    group_model = apps.get_model("courses", "Group")

    for _attempt in range(50):
        code = "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(length))

        if not group_model.objects.filter(invite_code=code).exists():
            return code

    raise RuntimeError("Nem sikerült szabad meghivókódot találni.")


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
    topic = models.ForeignKey(
        "bank.Topic",
        # Null only so that the lessons created before this field existed
        # survive the migration. New ones must name their topic: the task
        # drawing has no other way to know what to hand out.
        null=True,
        on_delete=models.PROTECT,
        related_name="class_sessions",
        verbose_name="témakör",
    )
    name = models.CharField(
        "rövid név",
        max_length=120,
        blank=True,
        help_text="Üresen hagyva a témakör neve jelenik meg. Pl. LNKO, Kongruenciák II.",
    )
    state = models.CharField("állapot", max_length=16, choices=State.choices, default=State.PLANNED)
    opened_at = models.DateTimeField("megnyitva", null=True, blank=True)
    closed_at = models.DateTimeField("lezárva", null=True, blank=True)
    counts_towards_grade = models.BooleanField("pontba számít", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "óra"
        verbose_name_plural = "órák"

    def __str__(self):
        return f"{self.group} – {self.display_name}"

    @property
    def display_name(self):
        """What to show on the page: the short name, or the topic it belongs to."""
        if self.name:
            return self.name

        if self.topic_id is not None:
            return self.topic.name

        return str(self.created_at.date())

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
