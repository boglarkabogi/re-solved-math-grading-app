from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Felhasznalo, KulsoAzonosito


@admin.register(Felhasznalo)
class FelhasznaloAdmin(UserAdmin):
    list_display = ("email", "username", "szerep", "neptun_kod", "is_staff")
    list_filter = ("szerep", "is_staff", "is_active")
    search_fields = ("email", "username", "neptun_kod", "last_name", "first_name")
    ordering = ("email",)
    fieldsets = UserAdmin.fieldsets + (("Dimat", {"fields": ("neptun_kod", "szerep", "azonosito")}),)
    readonly_fields = ("azonosito",)


admin.site.register(KulsoAzonosito)
