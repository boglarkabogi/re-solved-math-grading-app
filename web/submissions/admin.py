from django.contrib import admin

from .models import Assignment, Evaluation, OcrAttempt, Submission


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
