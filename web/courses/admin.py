from django.contrib import admin

from .models import Class, Course, Group, Member, PracticePermission


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "term")


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "course", "invite_code")
    search_fields = ("name", "invite_code")


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ("__str__", "state", "counts_towards_grade", "opened_at", "closed_at")
    list_filter = ("state", "group")


admin.site.register(Member)
admin.site.register(PracticePermission)
