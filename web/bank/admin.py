from django.contrib import admin

from .models import TaskBank, Topic


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(TaskBank)
class TaskBankAdmin(admin.ModelAdmin):
    list_display = ("code", "topic", "use", "active")
    list_filter = ("topic", "use", "active")
    search_fields = ("code", "task_text", "correct_solution")
