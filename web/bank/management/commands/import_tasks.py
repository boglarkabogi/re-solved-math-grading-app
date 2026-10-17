"""Import tasks into the task bank from a CSV or JSON file.

    python web/manage.py import_tasks data/tasks.csv
    python web/manage.py import_tasks data/tasks.csv --dry-run

Required columns / keys: topic, code, task_text, correct_solution
Optional: topic_name, use, comment, active

The column names match the model field names, so there is nothing to translate.
Safe to run again: existing tasks are matched by `code` and updated, so you never
get duplicates. That makes the CSV the single source of the task bank: edit it,
run the command again.
"""

import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bank.models import TaskBank, Topic

REQUIRED_COLUMNS = ("topic", "code", "task_text", "correct_solution")
TRUE_VALUES = {"1", "yes", "true", "igen", "x"}


class DryRun(Exception):
    """Internal signal for --dry-run: rolls the transaction back."""


def read_rows(path: Path):
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("tasks", [])
        return list(data)
    # utf-8-sig also swallows the BOM that Windows Excel writes
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_bool(value, default=True):
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in TRUE_VALUES


class Command(BaseCommand):
    help = "Import tasks into the task bank from a CSV or JSON file"

    def add_arguments(self, parser):
        parser.add_argument("file", help="the .csv or .json file to import")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="show what would happen without writing to the database",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"No such file: {path}")

        rows = read_rows(path)
        if not rows:
            raise CommandError("The file contains no rows.")

        missing = [column for column in REQUIRED_COLUMNS if column not in rows[0]]
        if missing:
            raise CommandError(f"Missing columns: {', '.join(missing)}")

        allowed_uses = {choice.value for choice in TaskBank.Use}
        created_count, updated_count, skipped_count = 0, 0, 0

        try:
            with transaction.atomic():
                for line_number, row in enumerate(rows, start=2):
                    code = (row.get("code") or "").strip()
                    if not code:
                        self.stderr.write(f"line {line_number}: no code, skipped")
                        skipped_count += 1
                        continue

                    use = (row.get("use") or "").strip() or TaskBank.Use.BOTH
                    if use not in allowed_uses:
                        raise CommandError(
                            f"line {line_number}: unknown use {use!r}. "
                            f"Allowed: {', '.join(sorted(allowed_uses))}"
                        )

                    topic_code = (row.get("topic") or "").strip()
                    topic, _ = Topic.objects.get_or_create(
                        code=topic_code,
                        defaults={"name": (row.get("topic_name") or topic_code).strip()},
                    )

                    _, created = TaskBank.objects.update_or_create(
                        code=code,
                        defaults={
                            "topic": topic,
                            "task_text": (row.get("task_text") or "").strip(),
                            "correct_solution": (row.get("correct_solution") or "").strip(),
                            "use": use,
                            "comment": (row.get("comment") or "").strip(),
                            "active": as_bool(row.get("active")),
                        },
                    )
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                if options["dry_run"]:
                    raise DryRun

        except DryRun:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN - nothing was written. Would create: {created_count}, "
                    f"update: {updated_count}, skip: {skipped_count}"
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {created_count}, updated: {updated_count}, skipped: {skipped_count}"
            )
        )
