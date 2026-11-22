from django.contrib import admin

from .models import BenchmarkCase, BenchmarkResult, BenchmarkRun, TrialRun


@admin.register(TrialRun)
class TrialRunAdmin(admin.ModelAdmin):
    list_display = ("created_at", "model_name", "score", "expected_score", "confidence", "run_by")
    list_filter = ("model_name",)
    search_fields = ("task_text", "solution_text")
    readonly_fields = ("prompt", "raw_response")


@admin.register(BenchmarkCase)
class BenchmarkCaseAdmin(admin.ModelAdmin):
    list_display = ("label", "topic", "task_code", "expected_score", "created_at")
    list_filter = ("topic", "expected_score")
    search_fields = ("label", "task_code", "task_text", "solution_text")


@admin.register(BenchmarkRun)
class BenchmarkRunAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "topics",
        "model_name",
        "prompt_version",
        "match_count",
        "case_count",
        "mean_deviation",
    )
    list_filter = ("model_name", "prompt_version")
    readonly_fields = ("system_prompt",)

    @admin.display(description="témakör")
    def topics(self, obj):
        return obj.topic_summary


@admin.register(BenchmarkResult)
class BenchmarkResultAdmin(admin.ModelAdmin):
    list_display = ("created_at", "case_label", "topic_label", "run_model", "expected_score", "score", "confidence", "duration_ms")
    list_filter = ("topic_label", "expected_score", "score", "run", "run__model_name")
    search_fields = ("case__label", "topic_label", "reasoning")
    readonly_fields = ("raw_response", "reasoning", "error")

    @admin.display(description="modell", ordering="run__model_name")
    def run_model(self, obj):
        return obj.run.model_name or "–"
