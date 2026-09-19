"""Adatbázist érintő tesztek: a modellek alapvető viselkedése."""

import pytest

from bank.models import BankFeladat, Temakor
from courses.models import Csoport, Kurzus, Ora


@pytest.mark.django_db
def test_bankfeladat_letrehozasa():
    temakor = Temakor.objects.create(kod="lnko", nev="Legnagyobb közös osztó")
    feladat = BankFeladat.objects.create(
        temakor=temakor,
        kod="lnko-213-200",
        feladat_szoveg="Mennyi lnko(213, 200)?",
        helyes_megoldas="1",
    )
    assert feladat.aktiv is True
    assert feladat.hasznalat == BankFeladat.Hasznalat.MINDKETTO
    assert "lnko-213-200" in str(feladat)


@pytest.mark.django_db
def test_ora_allapota():
    kurzus = Kurzus.objects.create(nev="Dimat I.", felev="2026/27/1")
    csoport = Csoport.objects.create(kurzus=kurzus, nev="1. csoport", meghivokod="ABC123")
    ora = Ora.objects.create(csoport=csoport, nev="1. alkalom")

    assert ora.nyitott is False
    ora.allapot = Ora.Allapot.NYITOTT
    assert ora.nyitott is True
