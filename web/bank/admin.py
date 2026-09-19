from django.contrib import admin

from .models import BankFeladat, Temakor


@admin.register(Temakor)
class TemakorAdmin(admin.ModelAdmin):
    list_display = ("nev", "kod")


@admin.register(BankFeladat)
class BankFeladatAdmin(admin.ModelAdmin):
    list_display = ("kod", "temakor", "nehezseg", "hasznalat", "aktiv")
    list_filter = ("temakor", "hasznalat", "aktiv")
    search_fields = ("kod", "feladat_szoveg", "helyes_megoldas")
