from django.contrib import admin

from .models import BenchmarkCase, BenchmarkRun, TrialRun


@admin.register(TrialRun)
class TrialRunAdmin(admin.ModelAdmin):
    list_display = ("created_at", "model_name", "score", "confidence", "run_by")
    list_filter = ("model_name",)
    search_fields = ("task_text", "solution_text")


@admin.register(BenchmarkCase)
class BenchmarkCaseAdmin(admin.ModelAdmin):
    list_display = ("label", "expected_score", "created_at")
    search_fields = ("label", "task_text", "solution_text")


@admin.register(BenchmarkRun)
class BenchmarkRunAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "model_name",
        "prompt_version",
        "match_count",
        "case_count",
        "mean_deviation",
    )
    list_filter = ("model_name", "prompt_version")
