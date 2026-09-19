"""A válaszfeldolgozás tesztjei (hálózat nélkül futnak)."""

import pytest

from motor.parsing import extract_json, normalize_pont, strip_think_blocks


def test_think_blokk_eltavolitasa():
    assert strip_think_blocks('<think>hmm</think>{"a": 1}') == '{"a": 1}'


def test_json_kinyerese_szoveg_kozul():
    valasz = 'Íme az értékelés:\n{"pont": 0.75, "indoklas": "majdnem jó"}\nKösz!'
    assert extract_json(valasz)["pont"] == 0.75


def test_json_latex_kapcsos_zarojellel():
    valasz = '{"indoklas": "a \\\\frac{1}{2} miatt", "pont": 1}'
    assert extract_json(valasz)["pont"] == 1


@pytest.mark.parametrize("bemenet,vart", [(0.6, 0.5), ("0,8", 0.75), (1, 1.0), ("0.1", 0.0)])
def test_pont_normalizalasa(bemenet, vart):
    assert normalize_pont(bemenet) == vart
