from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User, ExternalId


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("email", "username", "role", "neptun_code", "is_staff")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("email", "username", "neptun_code", "last_name", "first_name")
    ordering = ("email",)
    fieldsets = DjangoUserAdmin.fieldsets + (("Diszkrét matematika", {"fields": ("neptun_code", "role", "public_id")}),)
    readonly_fields = ("public_id",)


admin.site.register(ExternalId)
