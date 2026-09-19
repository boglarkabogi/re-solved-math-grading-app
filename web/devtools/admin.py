from django.contrib import admin

from .models import ProbaFuttatas, RegressziosFutas, Teszteset


@admin.register(ProbaFuttatas)
class ProbaFuttatasAdmin(admin.ModelAdmin):
    list_display = ("letrehozva", "modell", "pont", "magabiztossag", "futtatta")
    list_filter = ("modell",)


@admin.register(Teszteset)
class TesztesetAdmin(admin.ModelAdmin):
    list_display = ("cimke", "elvart_pont", "letrehozva")


admin.site.register(RegressziosFutas)
