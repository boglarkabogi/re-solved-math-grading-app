"""Reading benchmark cases out of a CSV file.

The file is written by hand or exported from a spreadsheet, so it has to
survive the usual damage: a BOM from Excel, semicolons instead of commas,
Hungarian decimal commas, and columns in any order.
"""

import csv
import io
from decimal import Decimal, InvalidOperation

from bank.models import TaskBank

ALLOWED_SCORES = (Decimal("0"), Decimal("0.25"), Decimal("0.5"), Decimal("0.75"), Decimal("1"))

# Minden oszlop neve magyarul is es angolul is elfogadott.
COLUMNS = {
    "label": ("label", "cimke", "címke"),
    "task_code": ("task_code", "feladat_kod", "feladat_kód", "kod", "kód"),
    "task_text": ("task_text", "feladat"),
    "correct_solution": ("correct_solution", "helyes_megoldas", "helyes_megoldás"),
    "solution_text": ("solution_text", "megoldas", "megoldás", "diak_megoldasa"),
    "expected_score": ("expected_score", "elvart_pont", "elvárt_pont", "pont"),
    "comment": ("comment", "megjegyzes", "megjegyzés"),
}


class CsvError(Exception):
    """A problem the person uploading the file can fix."""


def _normalise(name):
    return (name or "").strip().lower().replace(" ", "_").lstrip("﻿")


def _column_map(fieldnames):
    """Map the file's own header names onto our field names."""
    found = {}

    for raw in fieldnames or []:
        name = _normalise(raw)

        for field, spellings in COLUMNS.items():
            if name in spellings:
                found[field] = raw

    return found


def _read_score(raw, line_number):
    text = (raw or "").strip().replace(",", ".")

    if not text:
        raise CsvError(f"{line_number}. sor: hiányzik az elvárt pont.")

    try:
        score = Decimal(text)
    except InvalidOperation as error:
        raise CsvError(f"{line_number}. sor: az elvárt pont nem szám: {raw!r}") from error

    if score not in ALLOWED_SCORES:
        allowed = ", ".join(str(value) for value in ALLOWED_SCORES)
        raise CsvError(f"{line_number}. sor: az elvárt pont csak ez lehet: {allowed}. Kapott: {raw!r}")

    return score


def _reader(raw_bytes):
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Az Excel magyar Windowson gyakran ANSI-ban ment.
        text = raw_bytes.decode("cp1250", errors="replace")

    sample = text[:2048]

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    return csv.DictReader(io.StringIO(text), dialect=dialect)


def read_cases(raw_bytes):
    """Return the rows as dicts ready for BenchmarkCase(**row).

    A row may name a task from the bank with `task_code` instead of repeating
    the task text and the reference solution.
    """
    reader = _reader(raw_bytes)
    columns = _column_map(reader.fieldnames)

    if "expected_score" not in columns or "solution_text" not in columns:
        raise CsvError(
            "A fájlból hiányzik a megoldás vagy az elvárt pont oszlop. "
            "Kötelező: solution_text és expected_score (magyarul: megoldas, elvart_pont)."
        )

    cases = []

    for line_number, row in enumerate(reader, start=2):
        # The file's own column names, read into our field names.
        cell = {field: (row.get(column) or "").strip() for field, column in columns.items()}

        if not any(cell.values()):
            continue  # ures sor

        task_text = cell.get("task_text", "")
        correct_solution = cell.get("correct_solution", "")
        code = cell.get("task_code", "")

        if code:
            task = TaskBank.objects.filter(code=code).select_related("topic").first()

            if task is None:
                raise CsvError(f"{line_number}. sor: nincs ilyen feladat a bankban: {code!r}")

            task_text = task_text or task.task_text
            correct_solution = correct_solution or task.correct_solution

        if not task_text or not correct_solution:
            raise CsvError(
                f"{line_number}. sor: a feladat vagy a helyes megoldás üres, és nincs megadva feladatkód sem."
            )

        if not cell.get("solution_text"):
            raise CsvError(f"{line_number}. sor: a diák megoldása üres.")

        cases.append(
            {
                "label": cell.get("label") or code or f"sor-{line_number}",
                "task_text": task_text,
                "correct_solution": correct_solution,
                "solution_text": cell["solution_text"],
                "expected_score": _read_score(row.get(columns["expected_score"]), line_number),
                "comment": cell.get("comment", ""),
            }
        )

    if not cases:
        raise CsvError("A fájlban nincs egyetlen értékelhető sor sem.")

    return cases
