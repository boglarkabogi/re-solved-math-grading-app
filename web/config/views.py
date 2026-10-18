import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from recognition.service import recognise_solution

from bank.models import TaskBank, Topic
from courses.models import Class, Group, Member
from submissions.models import Assignment, OcrAttempt, Submission

logger = logging.getLogger(__name__)

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

            messages.success(request, "Registration successful. You can now log in.")

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
            group = Group.objects.select_related("course").get(invite_code=invite_code)
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
            messages.info(request, "You are already a member of this course.")
        else:
            messages.success(request, f"You joined {group.course.name} successfully.")

        return redirect("home")

    memberships = (
        Member.objects.filter(user=request.user)
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
        messages.error(request, "You are not a member of this course.")
        return redirect("home")

    lesson_ids = list(Class.objects.filter(group=lesson.group).order_by("id").values_list("id", flat=True))

    lesson_number = lesson_ids.index(lesson.id) + 1

    assignment = (
        Assignment.objects.filter(
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

        # Assignment exists, but no image has been uploaded yet.
        if submission is None or submission.state == Submission.State.ASSIGNED:
            return redirect(
                "generated_assignment",
                group_id=group_id,
                lesson_id=lesson_id,
            )

        # An image already exists.
        # Continue from the recognition page instead of showing upload again.
        if submission.state in [
            Submission.State.IMAGE_UPLOADED,
            Submission.State.OCR_RUNNING,
            Submission.State.OCR_DONE,
        ]:
            return redirect(
                "ocr_recognition",
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
        messages.error(request, "You are not a member of this course.")
        return redirect("home")

    # Ha már van feladata ehhez a lessonhöz,
    # nem generálunk másodikat.
    assignment = Assignment.objects.filter(
        student=request.user,
        session=lesson,
        mode=Assignment.Mode.CLASS,
    ).first()

    if assignment is not None:
        return redirect(
            "generated_assignment",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    # A Class.name nálunk maga a topic neve.
    topic = Topic.objects.filter(name__iexact=lesson.name).first()

    if topic is None:
        messages.error(request, f"No task topic exists for {lesson.name}.")
        return redirect(
            "lesson_detail",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    # Csak aktív, órai használatra engedélyezett feladatok.
    task = (
        TaskBank.objects.filter(
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
        messages.error(request, f"No active assignments are available for {lesson.name}.")
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
        messages.error(request, "You are not a member of this course.")
        return redirect("home")

    lesson_ids = list(Class.objects.filter(group=lesson.group).order_by("id").values_list("id", flat=True))

    lesson_number = lesson_ids.index(lesson.id) + 1

    assignment = (
        Assignment.objects.filter(
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

    submission, _ = Submission.objects.get_or_create(assignment=assignment)

    if request.method == "POST":
        image = request.FILES.get("solution_image")

        if image is None:
            messages.error(request, "Please select an image.")

        elif image.size > 20 * 1024 * 1024:
            messages.error(request, "The image must be smaller than 20 MB.")

        elif image.content_type not in [
            "image/jpeg",
            "image/png",
        ]:
            messages.error(request, "Only JPG, JPEG and PNG images are allowed.")

        else:
            OcrAttempt.objects.create(
                submission=submission,
                image=image,
            )

            submission.state = Submission.State.IMAGE_UPLOADED
            submission.save(update_fields=["state"])

            url = reverse(
                "ocr_recognition",
                kwargs={
                    "group_id": group_id,
                    "lesson_id": lesson_id,
                },
            )

            return redirect(f"{url}?autostart=1")

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

    ocr_attempt = submission.ocr_attempts.order_by("-created_at").first()

    if ocr_attempt is None:
        return redirect(
            "generated_assignment",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    # Run OCR
    if request.method == "POST":
        # Maximum 3 OCR runs for this uploaded image
        if ocr_attempt.ocr_run_count >= 3:
            messages.error(request, "You have already used all 3 recognition attempts for this image.")

            return redirect(
                "ocr_recognition",
                group_id=group_id,
                lesson_id=lesson_id,
            )

        logger.info(
            "OCR request started: user=%s submission=%s ocr_attempt=%s run=%s image=%s",
            request.user.id,
            submission.id,
            ocr_attempt.id,
            ocr_attempt.ocr_run_count + 1,
            ocr_attempt.image.name,
        )

        submission.state = Submission.State.OCR_RUNNING
        submission.save(update_fields=["state"])

        try:
            logger.info(
                "Calling recognise_solution: task=%s",
                assignment.task.code,
            )

            result = recognise_solution(
                image_field=ocr_attempt.image,
                task_text=assignment.task.task_text,
            )

            logger.info(
                "recognise_solution returned successfully: model=%s text_length=%s",
                result.get("model_name"),
                len(result.get("text", "")),
            )

            ocr_attempt.ocr_text = result["text"]
            ocr_attempt.model_name = result["model_name"]
            ocr_attempt.ocr_run_count += 1

            ocr_attempt.save(
                update_fields=[
                    "ocr_text",
                    "model_name",
                    "ocr_run_count",
                ]
            )

            submission.state = Submission.State.OCR_DONE
            submission.save(update_fields=["state"])

            logger.info(
                "OCR result saved successfully: ocr_attempt=%s run_count=%s",
                ocr_attempt.id,
                ocr_attempt.ocr_run_count,
            )

        except Exception:
            logger.exception(
                "OCR request failed: user=%s submission=%s ocr_attempt=%s",
                request.user.id,
                submission.id,
                ocr_attempt.id,
            )

            # Keep the uploaded image if the API fails
            submission.state = Submission.State.IMAGE_UPLOADED
            submission.save(update_fields=["state"])

            messages.error(request, "Recognition failed. Check the server logs for details.")

            return redirect(
                "ocr_recognition",
                group_id=group_id,
                lesson_id=lesson_id,
            )

        return redirect(
            "ocr_recognition",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    lesson_ids = list(Class.objects.filter(group=lesson.group).order_by("id").values_list("id", flat=True))

    lesson_number = lesson_ids.index(lesson.id) + 1

    attempt = ocr_attempt.ocr_run_count

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
def evaluation(request, group_id, lesson_id):
    """The evaluation step of the submission flow.
 
    GET  = show the result
    POST = either start the evaluation, or send feedback to the teacher about
           an evaluation that already happened. A successful evaluation is
           final: the student cannot run it again.
    """
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
        messages.error(request, "You are not a member of this course.")
        return redirect("home")
 
    assignment = get_object_or_404(
        Assignment.objects.select_related("task", "task__topic"),
        student=request.user,
        session=lesson,
        mode=Assignment.Mode.CLASS,
    )
 
    submission = get_object_or_404(Submission, assignment=assignment)
 
    ocr_attempt = submission.ocr_attempts.order_by("-created_at").first()
 
    # Without recognised text there is nothing to evaluate.
    if ocr_attempt is None or not ocr_attempt.ocr_text:
        messages.error(request, "Run the recognition before asking for an evaluation.")
        return redirect(
            "ocr_recognition",
            group_id=group_id,
            lesson_id=lesson_id,
        )
 
    if request.method == "POST":
        # Two different forms post here: the feedback box carries
        # "student_feedback", anything else means "start the evaluation".
        if "student_feedback" in request.POST:
            _save_feedback(request, submission)
        else:
            _start_evaluation(request, submission, ocr_attempt)
 
        return redirect(
            "evaluation",
            group_id=group_id,
            lesson_id=lesson_id,
        )
 
    lesson_ids = list(Class.objects.filter(group=lesson.group).order_by("id").values_list("id", flat=True))
 
    return render(
        request,
        "evaluation.html",
        {
            "lesson": lesson,
            "lesson_number": lesson_ids.index(lesson.id) + 1,
            "group": lesson.group,
            "course": lesson.group.course,
            "assignment": assignment,
            "submission": submission,
            "ocr_attempt": ocr_attempt,
            "evaluation": submission.evaluations.first(),
        },
    )
 
 
def _start_evaluation(request, submission, ocr_attempt):
    """Run the grading engine, unless this submission is already graded."""
    if submission.state == Submission.State.GRADED:
        # A finished evaluation is final. Re-running it would let a student
        # keep trying until a better score comes out.
        messages.error(request, "This submission has already been evaluated.")
        return
 
    # The comment about the recognised text arrives from the recognition page
    # and is an input to grade(). Other buttons post without the field, and
    # then we keep what the student wrote earlier.
    if "student_note" in request.POST:
        submission.student_note = request.POST.get("student_note", "").strip()
        submission.save(update_fields=["student_note"])
 
    logger.info(
        "Evaluation requested: user=%s submission=%s note_length=%s",
        request.user.id,
        submission.id,
        len(submission.student_note),
    )
 
    # TODO (next step): call motor.grading.grade() and save an Evaluation.
 
 
def _save_feedback(request, submission):
    """Store what the student wants the teacher to look at."""
    evaluation_result = submission.evaluations.first()
 
    if evaluation_result is None:
        messages.error(request, "There is no evaluation to give feedback on yet.")
        return
 
    evaluation_result.student_feedback = request.POST.get("student_feedback", "").strip()
    evaluation_result.student_feedback_at = timezone.now()
    evaluation_result.save(update_fields=["student_feedback", "student_feedback_at"])
 
    # This is what puts the submission on the teacher's review list.
    submission.needs_review = True
    submission.save(update_fields=["needs_review"])
 
    logger.info(
        "Student feedback saved: user=%s submission=%s evaluation=%s",
        request.user.id,
        submission.id,
        evaluation_result.id,
    )
 
    messages.success(request, "Your feedback was sent to the teacher.")

@login_required
def course_detail(request, group_id):
    membership = (
        Member.objects.select_related("group__course")
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

            messages.success(request, f"You left {course_name}.")

    return redirect("home")
