from django.contrib import admin

from .models import Csoport, GyakorlasEngedely, Kurzus, Ora, Tagsag


@admin.register(Kurzus)
class KurzusAdmin(admin.ModelAdmin):
    list_display = ("nev", "felev")


@admin.register(Csoport)
class CsoportAdmin(admin.ModelAdmin):
    list_display = ("nev", "kurzus", "meghivokod")
    search_fields = ("nev", "meghivokod")


@admin.register(Ora)
class OraAdmin(admin.ModelAdmin):
    list_display = ("__str__", "allapot", "pontba_szamit", "nyitva_ekkor", "zarva_ekkor")
    list_filter = ("allapot", "csoport")


admin.site.register(Tagsag)
admin.site.register(GyakorlasEngedely)
