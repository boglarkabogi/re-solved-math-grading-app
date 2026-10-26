from django.urls import path

from . import views

app_name = "devtools"

urlpatterns = [
    path("", views.trial_run, name="trial-run"),
    path("runs/<int:run_id>/", views.trial_run_detail, name="trial-run-detail"),
    path("cases/import/", views.import_cases, name="import-cases"),
    path("benchmark/start/", views.benchmark_start, name="benchmark-start"),
    path("benchmark/<int:run_id>/step/", views.benchmark_step, name="benchmark-step"),
]
