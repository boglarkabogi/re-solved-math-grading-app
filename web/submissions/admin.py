from django.contrib import admin

from .models import Beadas, Ertekeles, Kiosztas, OcrKiserlet


class OcrKiserletInline(admin.TabularInline):
    model = OcrKiserlet
    extra = 0


class ErtekelesInline(admin.StackedInline):
    model = Ertekeles
    extra = 0


@admin.register(Beadas)
class BeadasAdmin(admin.ModelAdmin):
    list_display = ("__str__", "allapot", "ellenorizendo", "letrehozva")
    list_filter = ("allapot", "ellenorizendo")
    inlines = [OcrKiserletInline, ErtekelesInline]


admin.site.register(Kiosztas)
admin.site.register(Ertekeles)
