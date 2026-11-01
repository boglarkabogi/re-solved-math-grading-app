"""The invite code is generated, not typed."""

import pytest
from django.urls import reverse

from courses.admin import GroupForm
from courses.models import INVITE_CODE_ALPHABET, Course, Group, Member, generate_invite_code


@pytest.fixture
def course(db):
    return Course.objects.create(name="Dimat I.", term="2026/27/1")


@pytest.mark.django_db
def test_a_generated_code_is_six_readable_characters():
    code = generate_invite_code()

    assert len(code) == 6
    assert all(character in INVITE_CODE_ALPHABET for character in code)


def test_the_alphabet_leaves_out_the_characters_students_confuse():
    for character in "O0I1":
        assert character not in INVITE_CODE_ALPHABET


@pytest.mark.django_db
def test_a_code_already_in_use_is_not_handed_out_again(monkeypatch, course):
    Group.objects.create(course=course, name="1. csoport", invite_code="A")

    draws = iter("AB")
    monkeypatch.setattr("courses.models.secrets.choice", lambda alphabet: next(draws))

    # The first draw is the code that group already holds, so another is made.
    assert generate_invite_code(length=1) == "B"


@pytest.mark.django_db
def test_an_empty_code_is_filled_on_save(course):
    form = GroupForm(data={"course": course.pk, "name": "2. csoport", "invite_code": ""})

    assert form.is_valid(), form.errors

    group = form.save()

    assert len(group.invite_code) == 6


@pytest.mark.django_db
def test_a_typed_code_is_kept_and_upper_cased(course):
    form = GroupForm(data={"course": course.pk, "name": "3. csoport", "invite_code": " dimat1 "})

    assert form.is_valid(), form.errors
    assert form.cleaned_data["invite_code"] == "DIMAT1"


@pytest.mark.django_db
def test_the_admin_action_gives_every_selected_group_a_new_code(course, rf):
    from django.contrib import admin
    from django.contrib.messages.storage.fallback import FallbackStorage

    group = Group.objects.create(course=course, name="1. csoport", invite_code="OLDONE")

    request = rf.post("/admin/courses/group/")
    request.session = {}
    request._messages = FallbackStorage(request)

    group_admin = admin.site._registry[Group]
    group_admin.regenerate_invite_codes(request, Group.objects.all())

    group.refresh_from_db()
    assert group.invite_code != "OLDONE"
    assert len(group.invite_code) == 6

@pytest.mark.django_db
def test_a_student_cannot_join_two_groups_of_the_same_course(client, world, make_student):
    """Two groups would mean two assignments for the same lesson topic."""
    student = world["student"]
    other_group = Group.objects.create(
        course=world["group"].course,
        name="2. csoport",
        invite_code="MASIKKOD",
    )

    client.force_login(student)

    answer = client.post(reverse("home"), {"invite_code": "MASIKKOD"}, follow=True)

    messages = [str(m) for m in answer.context["messages"]]
    assert any("already in another group" in m for m in messages)
    assert not Member.objects.filter(user=student, group=other_group).exists()


@pytest.mark.django_db
def test_joining_a_different_course_is_still_allowed(client, world, make_student):
    other = Group.objects.create(
        course=Course.objects.create(name="Analízis I."),
        name="1. csoport",
        invite_code="ANALIZIS",
    )

    client.force_login(world["student"])

    client.post(reverse("home"), {"invite_code": "ANALIZIS"}, follow=True)

    assert Member.objects.filter(user=world["student"], group=other).exists()


@pytest.mark.django_db
def test_a_lowercase_code_is_accepted(client, world, make_student):
    """The codes are printed in capitals; a student may type them in lower case."""
    group = Group.objects.create(
        course=Course.objects.create(name="Analízis I."),
        name="1. csoport",
        invite_code="ANALIZIS",
    )

    client.force_login(world["student"])

    client.post(reverse("home"), {"invite_code": "analizis"}, follow=True)

    assert Member.objects.filter(user=world["student"], group=group).exists()
