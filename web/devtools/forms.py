from django import forms


class TrialRunForm(forms.Form):
    """Run the grader on a solution you type in, skipping the recognition step."""

    task_text = forms.CharField(
        label="Feladat",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Mennyi lnko(213, 200)?"}),
    )
    correct_solution = forms.CharField(
        label="Helyes megoldás",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "1"}),
        help_text="Ez megy bele a promptba, hogy a modellnek ne kelljen magának számolnia.",
    )
    solution_text = forms.CharField(
        label="A diák megoldása (OCR-szöveg)",
        widget=forms.Textarea(attrs={"rows": 10}),
    )
    student_note = forms.CharField(
        label="A diák megjegyzése a felismerési hibáról",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "a 3. sorban 144 van, nem 134"}),
    )
    model_name = forms.CharField(
        label="Modell",
        required=False,
        help_text="Üresen a LLM_GRADING_MODEL fut. Ide másik modellt írva összehasonlíthatod őket.",
    )

    expected_score = forms.DecimalField(
        label="Elvárt pont",
        required=False,
        min_value=0,
        max_value=1,
        decimal_places=2,
        help_text="Amennyit te adnál rá. 0 / 0.25 / 0.5 / 0.75 / 1",
    )
    label = forms.CharField(
        label="Címke",
        required=False,
        help_text="Csak a tesztesethez, hogy később felismerd. Pl. lnko-nagy-szamok.",
    )
    save_as_benchmark_case = forms.BooleanField(
        label="Mentés tesztesetként (regressziós készlet)",
        required=False,
    )

    def clean(self):
        data = super().clean()
        if data.get("save_as_benchmark_case") and data.get("expected_score") is None:
            self.add_error("expected_score", "Tesztesethez meg kell adni az elvárt pontot.")
        return data


class BenchmarkCsvForm(forms.Form):
    """Loading several cases at once, instead of typing them one by one."""

    csv_file = forms.FileField(
        label="CSV fájl",
        help_text=(
            "Oszlopok: label, task_code, task_text, correct_solution, solution_text, "
            "expected_score, comment. Magyar nevek is mennek. Pontosvessző és vessző is jó "
            "elválasztónak. A task_code megadásával a feladat és a helyes megoldás a "
            "feladatbankból jön."
        ),
    )
    replace_existing = forms.BooleanField(
        label="A meglévő tesztesetek törlése betöltés előtt",
        required=False,
        help_text="Enélkül az új esetek a meglévők mellé kerülnek.",
    )


class BenchmarkRunForm(forms.Form):
    """Starting a run over the whole case set."""

    model_name = forms.CharField(
        label="Modell",
        required=False,
        help_text="Üresen a LLM_GRADING_MODEL fut.",
    )
    prompt_version = forms.CharField(
        label="A prompt verziója",
        required=False,
        help_text="Szabad szöveg, hogy később tudd, melyik prompttal mért a futás. Pl. v3-szigorubb.",
    )
