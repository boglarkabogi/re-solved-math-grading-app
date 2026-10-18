"""Tests for motor/parsing.py. Run from the project root:  python -m pytest"""

import pytest

from motor.parsing import extract_json, normalize_score, strip_think_blocks

# ============================================================
# strip_think_blocks
# ============================================================


def test_think_block_is_removed():
    assert strip_think_blocks("<think>gondolkodom</think>válasz") == "válasz"


def test_multiline_think_block_is_removed():
    text = "<think>\n1. sor\n2. sor\n</think>\n\nválasz"
    assert strip_think_blocks(text) == "válasz"


def test_several_think_blocks_are_removed():
    assert strip_think_blocks("<think>a</think>X<think>b</think>Y") == "XY"


def test_text_without_think_is_only_trimmed():
    assert strip_think_blocks("  sima szöveg  ") == "sima szöveg"


@pytest.mark.parametrize("empty", [None, ""])
def test_empty_input_gives_empty_string(empty):
    assert strip_think_blocks(empty) == ""


# ============================================================
# extract_json
# ============================================================


def test_plain_json():
    assert extract_json('{"pont": 1, "indoklas": "jó"}') == {"pont": 1, "indoklas": "jó"}


def test_json_surrounded_by_prose():
    response = 'Íme az értékelés:\n{"pont": 0.5}\nRemélem, segít!'
    assert extract_json(response) == {"pont": 0.5}


def test_json_inside_a_markdown_code_block():
    response = '```json\n{"pont": 0.75}\n```'
    assert extract_json(response) == {"pont": 0.75}


def test_braces_inside_a_think_block_are_ignored():
    # the {...} in the reasoning must not be mistaken for the answer
    response = '<think>talán {pont: 0}? nem...</think>{"pont": 1}'
    assert extract_json(response) == {"pont": 1}


def test_latex_backslashes_in_the_text_are_repaired():
    # \gcd and \in are invalid JSON escapes, the parser has to fix them
    response = r'{"indoklas": "\gcd(a, b) = 1, x \in Z_5"}'
    assert extract_json(response) == {"indoklas": r"\gcd(a, b) = 1, x \in Z_5"}


def test_valid_escapes_are_left_alone():
    response = r'{"indoklas": "1. sor\n2. sor, \"idézet\""}'
    assert extract_json(response) == {"indoklas": '1. sor\n2. sor, "idézet"'}


def test_braces_inside_a_string_do_not_count_as_depth():
    response = '{"feladat": "Z_5[x] = {0, 1, 2}", "pont": 1} utána szöveg'
    assert extract_json(response) == {"feladat": "Z_5[x] = {0, 1, 2}", "pont": 1}


def test_nested_object():
    response = '{"pont": 1, "reszletek": {"modszer": "jó"}}'
    assert extract_json(response) == {"pont": 1, "reszletek": {"modszer": "jó"}}


def test_the_first_of_two_objects_is_returned():
    assert extract_json('{"a": 1} {"b": 2}') == {"a": 1}


def test_accented_characters_survive():
    assert extract_json('{"indoklas": "Helyes módszer, jó végeredmény."}') == {
        "indoklas": "Helyes módszer, jó végeredmény."
    }


@pytest.mark.parametrize(
    "broken",
    [
        None,
        "",
        "nincs benne json",
        '{"pont": 1, "indoklas": "félbe',  # truncated response (e.g. token limit hit)
        "[1, 2, 3]",  # array, not an object
        "<think>csak gondolkodás</think>",
    ],
)
def test_unparsable_response_gives_none(broken):
    assert extract_json(broken) is None


# ============================================================
# normalize_score
# ============================================================


@pytest.mark.parametrize(
    ("given", "expected", "changed"),
    [
        (1, 1, False),
        (0, 0, False),
        (0.75, 0.75, False),
        (0.6, 0.5, True),  # nearest allowed value
        (0.7, 0.75, True),
        (0.9, 1, True),
        (0.1, 0, True),
        ("0.75", 0.75, False),  # a number arriving as text also works
        ("1", 1, False),
    ],
)
def test_score_is_moved_to_the_scale(given, expected, changed):
    result = {"pont": given}

    assert normalize_score(result) is changed

    assert result["pont"] == expected


@pytest.mark.parametrize("given", [5, -2, 1.5, 100])
def test_a_score_outside_the_scale_is_refused(given):
    """Pulling 5 onto the nearest allowed value would hand out full marks."""
    result = {"pont": given}

    assert normalize_score(result) is True
    assert result["pont"] is None
    assert "hiba" in result


@pytest.mark.parametrize("result", [{}, {"pont": None}, {"pont": "nem szám"}])
def test_a_missing_or_unusable_score_is_left_alone(result):
    assert normalize_score(result) is False


def test_it_modifies_in_place_and_reports_whether_it_had_to():
    # it still edits the dict; the return value is only the flag
    result = {"pont": 0.6, "indoklas": "x"}

    changed = normalize_score(result)

    assert changed is True
    assert result == {"pont": 0.5, "indoklas": "x"}
