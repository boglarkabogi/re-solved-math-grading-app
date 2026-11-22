import django.db.models.deletion
from django.db import migrations, models


def backfill_topics(apps, schema_editor):
    """A meglévő tesztesetekhez a feladat szövege alapján keresi meg a témakört."""
    BenchmarkCase = apps.get_model("devtools", "BenchmarkCase")
    BenchmarkResult = apps.get_model("devtools", "BenchmarkResult")
    TaskBank = apps.get_model("bank", "TaskBank")

    by_text = {}

    for task in TaskBank.objects.select_related("topic"):
        by_text.setdefault(task.task_text.strip(), task)

    for case in BenchmarkCase.objects.all():
        task = by_text.get(case.task_text.strip())

        if task is None:
            continue

        case.task_code = task.code
        case.topic_id = task.topic_id
        case.save(update_fields=["task_code", "topic"])

    for result in BenchmarkResult.objects.select_related("case__topic"):
        if result.case_id and result.case.topic_id and not result.topic_label:
            result.topic_label = result.case.topic.name
            result.save(update_fields=["topic_label"])


class Migration(migrations.Migration):

    dependencies = [
        ("devtools", "0005_benchmarkrun_system_prompt"),
        ("bank", "__first__"),
    ]

    operations = [
        migrations.AddField(
            model_name="benchmarkcase",
            name="task_code",
            field=models.CharField(blank=True, max_length=64, verbose_name="feladat kódja"),
        ),
        migrations.AddField(
            model_name="benchmarkcase",
            name="topic",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="benchmark_cases",
                to="bank.topic",
                verbose_name="témakör",
            ),
        ),
        migrations.AddField(
            model_name="benchmarkresult",
            name="topic_label",
            field=models.CharField(blank=True, max_length=120, verbose_name="témakör"),
        ),
        migrations.RunPython(backfill_topics, migrations.RunPython.noop),
    ]