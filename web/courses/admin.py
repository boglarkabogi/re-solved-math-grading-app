from django import forms
from django.contrib import admin

from bank.models import Topic

from .models import Class, Course, Group, Member, PracticePermission, generate_invite_code


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "term")


class GroupForm(forms.ModelForm):
    """The invite code does not have to be typed by hand.

    Left empty it is filled on save, and the button next to the field puts a
    fresh one in right away.
    """

    class Meta:
        model = Group
        fields = ("course", "name", "invite_code", "moodle_group_id")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["invite_code"].required = False
        self.fields[
            "invite_code"
        ].help_text = "Üresen hagyva mentéskor generálódik. A gombbal azonnal kérhetsz egy újat."

    def clean_invite_code(self):
        code = (self.cleaned_data.get("invite_code") or "").strip().upper()

        return code or generate_invite_code()


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    form = GroupForm
    list_display = ("name", "course", "invite_code")
    search_fields = ("name", "invite_code")
    actions = ["regenerate_invite_codes"]

    class Media:
        js = ("js/admin_invite_code.js",)

    @admin.action(description="Új meghívókód generálása")
    def regenerate_invite_codes(self, request, queryset):
        """Useful when a code has leaked outside the group."""
        for group in queryset:
            group.invite_code = generate_invite_code()
            group.save(update_fields=["invite_code"])

        self.message_user(request, f"{queryset.count()} csoport kapott új meghívókódot.")


class ClassForm(forms.ModelForm):
    """Setting up a lesson: pick the topic, name it only if you want to."""

    class Meta:
        model = Class
        fields = ("group", "topic", "name", "state", "counts_towards_grade", "opened_at", "closed_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["topic"].queryset = Topic.objects.order_by("name")
        self.fields["topic"].empty_label = "– válassz témakört –"


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    form = ClassForm
    list_display = ("__str__", "topic", "state", "counts_towards_grade", "opened_at", "closed_at")
    list_filter = ("state", "topic", "group")
    list_select_related = ("topic", "group", "group__course")


admin.site.register(Member)
admin.site.register(PracticePermission)
