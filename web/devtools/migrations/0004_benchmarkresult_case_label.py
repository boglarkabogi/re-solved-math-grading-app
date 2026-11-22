import django.db.models.deletion
from django.db import migrations, models


def fill_case_labels(apps, schema_editor):
    """A meglévő soroknak átmásolja a teszteset nevét, amíg még megvan."""
    BenchmarkResult = apps.get_model("devtools", "BenchmarkResult")

    for result in BenchmarkResult.objects.select_related("case").iterator():
        if result.case_id and not result.case_label:
            result.case_label = result.case.label
            result.save(update_fields=["case_label"])


class Migration(migrations.Migration):

    dependencies = [
        ("devtools", "0003_trialrun_expected_score"),
    ]

    operations = [
        migrations.AddField(
            model_name="benchmarkresult",
            name="case_label",
            field=models.CharField(blank=True, max_length=120, verbose_name="teszteset neve"),
        ),
        migrations.AlterField(
            model_name="benchmarkresult",
            name="case",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="results",
                to="devtools.benchmarkcase",
            ),
        ),
        migrations.AlterModelOptions(
            name="benchmarkresult",
            options={
                "ordering": ["pk"],
                "verbose_name": "teszteset eredménye",
                "verbose_name_plural": "tesztesetek eredményei",
            },
        ),
        migrations.RunPython(fill_case_labels, migrations.RunPython.noop),
    ]