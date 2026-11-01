from django.contrib import admin

from .models import Assignment, Evaluation, Job, OcrAttempt, Submission


class OcrAttemptInline(admin.TabularInline):
    model = OcrAttempt
    extra = 0


class EvaluationInline(admin.StackedInline):
    model = Evaluation
    extra = 0


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "state", "needs_review", "created_at")
    list_filter = ("state", "needs_review")
    inlines = [OcrAttemptInline, EvaluationInline]


admin.site.register(Assignment)
admin.site.register(Evaluation)

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    """The queue, and the measurement data it leaves behind.

    During a lesson this is where you can see whether the queue is moving;
    afterwards the waited and ran columns are the numbers for the measurement.
    """

    list_display = ("__str__", "kind", "state", "queued_at", "waited", "ran", "worker")
    list_filter = ("kind", "state")
    readonly_fields = ("queued_at", "started_at", "finished_at", "attempts", "worker", "error")
    date_hierarchy = "queued_at"

    @admin.display(description="várakozott (mp)")
    def waited(self, job):
        seconds = job.waited_seconds
        return "–" if seconds is None else f"{seconds:.1f}"

    @admin.display(description="futott (mp)")
    def ran(self, job):
        seconds = job.duration_seconds
        return "–" if seconds is None else f"{seconds:.1f}"
