from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.shortcuts import get_object_or_404
from django.db import transaction

from recognition.service import recognise_solution
from courses.models import Group, Member, Class
from submissions.models import Assignment, Submission, OcrAttempt
from bank.models import Topic, TaskBank

User = get_user_model()

def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    errors = {}

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        neptun_code = request.POST.get("neptun_code", "").strip().upper()
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")

        if not username:
            errors["username"] = "Username is required."

        elif User.objects.filter(username=username).exists():
            errors["username"] = "This username is already in use."

        if not email:
            errors["email"] = "E-mail address is required."

        elif User.objects.filter(email=email).exists():
            errors["email"] = "An account with this e-mail already exists."

        if neptun_code and len(neptun_code) != 6:
            errors["neptun_code"] = "Neptun code must contain 6 characters."

        if password1 != password2:
            errors["password2"] = "The passwords do not match."

        if password1 and password1 == password2:
            try:
                validate_password(password1)
            except ValidationError as error:
                errors["password1"] = " ".join(error.messages)

        if not errors:
            User.objects.create_user(
                username=username,
                email=email,
                neptun_code=neptun_code,
                password=password1,
                role="diak",
            )

            messages.success(
                request,
                "Registration successful. You can now log in."
            )

            return redirect("login")

    return render(
        request,
        "register.html",
        {
            "errors": errors,
        },
    )


@login_required
def home(request):
    if request.method == "POST":
        invite_code = request.POST.get("invite_code", "").strip()

        if not invite_code:
            messages.error(request, "Please enter a course code.")
            return redirect("home")

        try:
            group = Group.objects.select_related("course").get(
                invite_code=invite_code
            )
        except Group.DoesNotExist:
            messages.error(request, "Invalid course code.")
            return redirect("home")

        membership, created = Member.objects.get_or_create(
            user=request.user,
            group=group,
            defaults={
                "is_teacher": False,
            },
        )

        if not created:
            messages.info(
                request,
                "You are already a member of this course."
            )
        else:
            messages.success(
                request,
                f"You joined {group.course.name} successfully."
            )

        return redirect("home")

    memberships = (
        Member.objects
        .filter(user=request.user)
        .select_related("group__course")
        .prefetch_related("group__orak")
        .order_by("group__course__name", "group__name")
    )

    return render(
        request,
        "home.html",
        {
            "memberships": memberships,
        },
    )

@login_required
def lesson_detail(request, group_id, lesson_id):
    lesson = get_object_or_404(
        Class.objects.select_related("group__course"),
        id=lesson_id,
        group_id=group_id,
    )

    membership = Member.objects.filter(
        user=request.user,
        group=lesson.group,
    ).first()

    if membership is None:
        messages.error(
            request,
            "You are not a member of this course."
        )
        return redirect("home")

    lesson_ids = list(
        Class.objects
        .filter(group=lesson.group)
        .order_by("id")
        .values_list("id", flat=True)
    )

    lesson_number = lesson_ids.index(lesson.id) + 1

    assignment = (
        Assignment.objects
        .filter(
            student=request.user,
            session=lesson,
            mode=Assignment.Mode.CLASS,
        )
        .select_related("task", "task__topic")
        .first()
    )

    if assignment is not None:
        submission = getattr(
            assignment,
            "submission",
            None,
        )

        # Van generált feladat, de még nincs kép feltöltve.
        if (
            submission is None
            or submission.state == Submission.State.ASSIGNED
        ):
            return redirect(
                "generated_assignment",
                group_id=group_id,
                lesson_id=lesson_id,
            )

        # Már van feltöltött kép, vagy az OCR folyamatban/kész.
        if submission.state in [
            Submission.State.ASSIGNED,
            Submission.State.IMAGE_UPLOADED,
        ]:
            return redirect(
                "generated_assignment",
                group_id=group_id,
                lesson_id=lesson_id,
            )

        if submission.state in [
            Submission.State.OCR_RUNNING,
            Submission.State.OCR_DONE,
        ]:
            return redirect(
                "generated_assignment",
                group_id=group_id,
                lesson_id=lesson_id,
            )

    return render(
        request,
        "lesson.html",
        {
            "lesson": lesson,
            "lesson_number": lesson_number,
            "course": lesson.group.course,
            "group": lesson.group,
            "assignment": assignment,
        },
    )

@login_required
@transaction.atomic
def generate_assignment(request, group_id, lesson_id):
    if request.method != "POST":
        return redirect(
            "lesson_detail",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    lesson = get_object_or_404(
        Class.objects.select_related("group__course"),
        id=lesson_id,
        group_id=group_id,
    )

    membership = Member.objects.filter(
        user=request.user,
        group=lesson.group,
    ).first()

    if membership is None:
        messages.error(
            request,
            "You are not a member of this course."
        )
        return redirect("home")

    # Ha már van feladata ehhez a lessonhöz,
    # nem generálunk másodikat.
    assignment = (
        Assignment.objects
        .filter(
            student=request.user,
            session=lesson,
            mode=Assignment.Mode.CLASS,
        )
        .first()
    )

    if assignment is not None:
        return redirect(
            "generated_assignment",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    # A Class.name nálunk maga a topic neve.
    topic = Topic.objects.filter(
        name__iexact=lesson.name
    ).first()

    if topic is None:
        messages.error(
            request,
            f"No task topic exists for {lesson.name}."
        )
        return redirect(
            "lesson_detail",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    # Csak aktív, órai használatra engedélyezett feladatok.
    task = (
        TaskBank.objects
        .filter(
            topic=topic,
            active=True,
            use__in=[
                TaskBank.Use.CLASS,
                TaskBank.Use.BOTH,
            ],
        )
        .order_by("?")
        .first()
    )

    if task is None:
        messages.error(
            request,
            f"No active assignments are available for {lesson.name}."
        )
        return redirect(
            "lesson_detail",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    assignment = Assignment.objects.create(
        student=request.user,
        task=task,
        session=lesson,
        mode=Assignment.Mode.CLASS,
    )

    Submission.objects.create(
        assignment=assignment,
    )

    return redirect(
        "generated_assignment",
        group_id=group_id,
        lesson_id=lesson_id,
    )

@login_required
@transaction.atomic
def generated_assignment(request, group_id, lesson_id):
    lesson = get_object_or_404(
        Class.objects.select_related("group__course"),
        id=lesson_id,
        group_id=group_id,
    )

    membership = Member.objects.filter(
        user=request.user,
        group=lesson.group,
    ).first()

    if membership is None:
        messages.error(
            request,
            "You are not a member of this course."
        )
        return redirect("home")

    lesson_ids = list(
        Class.objects
        .filter(group=lesson.group)
        .order_by("id")
        .values_list("id", flat=True)
    )

    lesson_number = lesson_ids.index(lesson.id) + 1

    assignment = (
        Assignment.objects
        .filter(
            student=request.user,
            session=lesson,
            mode=Assignment.Mode.CLASS,
        )
        .select_related("task", "task__topic")
        .first()
    )

    if assignment is None:
        return redirect(
            "lesson_detail",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    submission, _ = Submission.objects.get_or_create(
        assignment=assignment
    )

    if request.method == "POST":
        image = request.FILES.get("solution_image")

        if image is None:
            messages.error(
                request,
                "Please select an image."
            )

        elif image.size > 20 * 1024 * 1024:
            messages.error(
                request,
                "The image must be smaller than 20 MB."
            )

        elif image.content_type not in [
            "image/jpeg",
            "image/png",
        ]:
            messages.error(
                request,
                "Only JPG, JPEG and PNG images are allowed."
            )

        else:
            ocr_attempt = OcrAttempt.objects.create(
                submission=submission,
                image=image,
            )

            submission.state = Submission.State.IMAGE_UPLOADED
            submission.save(update_fields=["state"])

            return redirect(
                "ocr_recognition",
                group_id=group_id,
                lesson_id=lesson_id,
            )

    attempt = submission.ocr_attempts.count() + 1
    attempt = max(1, min(attempt, 3))

    return render(
        request,
        "generated_assignment.html",
        {
            "lesson": lesson,
            "lesson_number": lesson_number,
            "course": lesson.group.course,
            "group": lesson.group,
            "assignment": assignment,
            "submission": submission,
            "attempt": attempt,
        },
    )

@login_required
def ocr_recognition(request, group_id, lesson_id):
    lesson = get_object_or_404(
        Class.objects.select_related("group__course"),
        id=lesson_id,
        group_id=group_id,
    )

    membership = Member.objects.filter(
        user=request.user,
        group=lesson.group,
    ).first()

    if membership is None:
        return redirect("home")

    assignment = get_object_or_404(
        Assignment.objects.select_related(
            "task",
            "task__topic",
        ),
        student=request.user,
        session=lesson,
        mode=Assignment.Mode.CLASS,
    )

    submission = get_object_or_404(
        Submission,
        assignment=assignment,
    )

    ocr_attempt = (
        submission.ocr_attempts
        .order_by("-created_at")
        .first()
    )

    if ocr_attempt is None:
        return redirect(
            "generated_assignment",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    # OCR tényleges indítása
    if request.method == "POST":

        # Ha már erre a képre lefutott az OCR,
        # ne hívjuk meg újra feleslegesen.
        if not ocr_attempt.ocr_text:

            submission.state = Submission.State.OCR_RUNNING
            submission.save(
                update_fields=["state"]
            )

            try:
                result = recognise_solution(
                    image_field=ocr_attempt.image,
                    task_text=assignment.task.task_text,
                )

                ocr_attempt.ocr_text = result["text"]
                ocr_attempt.model_name = result["model_name"]

                ocr_attempt.save(
                    update_fields=[
                        "ocr_text",
                        "model_name",
                    ]
                )

                submission.state = Submission.State.OCR_DONE
                submission.save(
                    update_fields=["state"]
                )

            except Exception as error:
                # Ha az API hibázik, a feltöltött kép ne vesszen el.
                # Visszaengedjük a usert step 2-re.
                submission.state = Submission.State.IMAGE_UPLOADED
                submission.save(
                    update_fields=["state"]
                )

                messages.error(
                    request,
                    f"Recognition failed: {error}"
                )

                return redirect(
                    "generated_assignment",
                    group_id=group_id,
                    lesson_id=lesson_id,
                )

        return redirect(
            "ocr_recognition",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    lesson_ids = list(
        Class.objects
        .filter(group=lesson.group)
        .order_by("id")
        .values_list("id", flat=True)
    )

    lesson_number = lesson_ids.index(lesson.id) + 1

    attempt = submission.ocr_attempts.count()
    attempt = max(1, min(attempt, 3))

    return render(
        request,
        "ocr_recognition.html",
        {
            "lesson": lesson,
            "lesson_number": lesson_number,
            "group": lesson.group,
            "course": lesson.group.course,
            "assignment": assignment,
            "submission": submission,
            "ocr_attempt": ocr_attempt,
            "attempt": attempt,
        },
    )

@login_required
def evaluation(request):
    attempt = int(request.GET.get("attempt", 1))
    attempt = max(1, min(attempt, 3))

    return render(
        request,
        "evaluation.html",
        {
            "attempt": attempt,
        },
    )

@login_required
def course_detail(request, group_id):
    membership = (
        Member.objects
        .select_related("group__course")
        .filter(
            user=request.user,
            group_id=group_id,
        )
        .first()
    )

    if membership is None:
        messages.error(request, "You are not a member of this course.")
        return redirect("home")

    return render(
        request,
        "course.html",
        {
            "membership": membership,
            "group": membership.group,
            "course": membership.group.course,
        },
    )


@login_required
def leave_course(request, group_id):
    if request.method == "POST":
        membership = Member.objects.filter(
            user=request.user,
            group_id=group_id,
        ).first()

        if membership is not None:
            course_name = membership.group.course.name
            membership.delete()

            messages.success(
                request,
                f"You left {course_name}."
            )

    return redirect("home")
