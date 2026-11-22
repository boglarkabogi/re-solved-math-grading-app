from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("devtools", "0004_benchmarkresult_case_label"),
    ]

    operations = [
        migrations.AddField(
            model_name="benchmarkrun",
            name="system_prompt",
            field=models.TextField(blank=True, verbose_name="a futtatáshoz használt prompt"),
        ),
    ]