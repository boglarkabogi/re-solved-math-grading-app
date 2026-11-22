import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from bank.models import TaskBank
from courses.models import Class, Group, Member
from submissions import queue
from submissions.models import Assignment, Job, OcrAttempt, Submission

logger = logging.getLogger(__name__)

User = get_user_model()

LESSON_STATUS = {
    Submission.State.ASSIGNED: {"label": "Task generated", "css": "generated"},
    Submission.State.IMAGE_UPLOADED: {"label": "Image uploaded", "css": "uploaded"},
    Submission.State.OCR_RUNNING: {"label": "Recognising…", "css": "uploaded"},
    Submission.State.OCR_DONE: {"label": "Text recognised", "css": "recognised"},
    Submission.State.GRADING: {"label": "Evaluating…", "css": "evaluating"},
    Submission.State.GRADED: {"label": "Evaluated", "css": "graded"},
    Submission.State.FAILED: {"label": "Needs attention", "css": "failed"},
}

LESSON_NOT_STARTED = {"label": "Not started", "css": "not-started"}


def _attach_lesson_status(user, memberships):
    """Put this student's own progress onto every lesson card.

    One query for the whole page: the lessons are already prefetched, so the
    status is written onto those cached objects.
    """
    states = dict(
        Submission.objects.filter(
            assignment__student=user,
            assignment__mode=Assignment.Mode.CLASS,
            assignment__session__isnull=False,
        ).values_list("assignment__session_id", "state")
    )

    for membership in memberships:
        for lesson in membership.group.orak.all():
            lesson.student_status = LESSON_STATUS.get(states.get(lesson.id), LESSON_NOT_STARTED)


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
            group = Group.objects.select_related("course").get(invite_code=invite_code.upper())
        except Group.DoesNotExist:
            messages.error(request, "Invalid course code.")
            return redirect("home")

        other = (
            Member.objects.filter(user=request.user, group__course=group.course)
            .exclude(group=group)
            .select_related("group")
            .first()
        )

        if other is not None:
            messages.error(
                request,
                f"You are already in another group of {group.course.name} "
                f"({other.group.name}). Ask your teacher to move you "
                f"if you need to change groups.",
            )
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

    memberships = list(
        Member.objects.filter(user=request.user)
        .select_related("group__course")
        .prefetch_related("group__orak")
        .order_by("group__course__name", "group__name")
    )

    _attach_lesson_status(request.user, memberships)

    return render(
        request,
        "home.html",
        {
            "memberships": memberships,
        },
    )


def _finished_redirect(submission, group_id, lesson_id):
    """Send the student to the result when the submission is already graded.

    A graded submission is closed. Without this guard the student could walk
    back through the flow, upload another image, run the recognition again and
    ask for a second opinion on a task that already has a score.
    """
    if submission is not None and submission.state == Submission.State.GRADED:
        return redirect(
            "evaluation",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    return None


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

    lesson_number = lesson.position

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

        if submission is not None and submission.state in [
            Submission.State.GRADING,
            Submission.State.GRADED,
            Submission.State.FAILED,
        ]:
            return redirect(
                "evaluation",
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

    if not lesson.is_open:
        if lesson.has_ended or lesson.state == Class.State.CLOSED:
            message = (
                "This lesson is closed, so no new task can be drawn. "
                "If you think this is a mistake, ask your teacher."
            )
        elif lesson.opened_at is not None:
            message = (
                "This lesson has not started yet. It opens on "
                f"{timezone.localtime(lesson.opened_at):%Y.%m.%d. %H:%M}."
            )
        else:
            message = "Your teacher has not opened this lesson yet."

        messages.error(request, message)

        return redirect(
            "lesson_detail",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    topic = lesson.topic

    if topic is None:
        messages.error(request, "This lesson has no topic set, so no task can be drawn.")
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

    lesson_number = lesson.position

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

    finished = _finished_redirect(submission, group_id, lesson_id)

    if finished is not None:
        messages.info(request, "This assignment has already been evaluated.")
        return finished

    if submission.ocr_in_progress:
        messages.warning(request, "Please wait until the current recognition finishes.")
        return redirect(
            "ocr_recognition",
            group_id=group_id,
            lesson_id=lesson_id,
        )

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

    attempt = min(submission.ocr_run_count + 1, 3)

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
        Assignment.objects.select_related("task", "task__topic"),
        student=request.user,
        session=lesson,
        mode=Assignment.Mode.CLASS,
    )

    submission = get_object_or_404(
        Submission,
        assignment=assignment,
    )

    finished = _finished_redirect(submission, group_id, lesson_id)

    if finished is not None:
        messages.info(request, "This assignment has already been evaluated.")
        return finished

    ocr_attempt = submission.ocr_attempts.order_by("-created_at").first()

    if ocr_attempt is None:
        return redirect(
            "generated_assignment",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    if request.method == "POST":
        # Atomically reserve the recognition slot.
        reserved = Submission.objects.filter(
            pk=submission.pk,
            ocr_run_count__lt=3,
            ocr_in_progress=False,
        ).update(
            ocr_in_progress=True,
            state=Submission.State.OCR_RUNNING,
        )

        if not reserved:
            submission.refresh_from_db()

            if submission.ocr_in_progress:
                messages.warning(
                    request,
                    "Recognition is already running.",
                )
            else:
                messages.error(
                    request,
                    "You have already used all 3 recognition attempts for this assignment.",
                )

            return redirect(
                "ocr_recognition",
                group_id=group_id,
                lesson_id=lesson_id,
            )

        job = queue.enqueue(submission, Job.Kind.OCR)

        logger.info(
            "Recognition queued: user=%s submission=%s job=%s run=%s",
            request.user.id,
            submission.id,
            job.id,
            submission.ocr_run_count + 1,
        )

        return redirect(
            "ocr_recognition",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    lesson_ids = list(Class.objects.filter(group=lesson.group).order_by("id").values_list("id", flat=True))

    lesson_number = lesson_ids.index(lesson.id) + 1

    attempt = submission.ocr_run_count

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
            "queued": _queue_state(submission),
        },
    )

def _queue_state(submission):
    """What the page should say about this submission's place in the queue.

    Returns None when nothing is queued or running for it, so a template can
    simply ask "is there a wait".
    """
    job = (
        submission.jobs.filter(state__in=[Job.State.QUEUED, Job.State.RUNNING]).order_by("queued_at").first()
    )

    if job is None:
        return None

    place = queue.position(job)

    return {
        "job": job,
        "kind": job.kind,
        "running": job.state == Job.State.RUNNING,
        "position": place,
        "wait_seconds": queue.wait_seconds(place),
    }


@login_required
def job_status(request, group_id, lesson_id):
    """Where the student's work stands, as JSON, for the waiting page.

    The waiting page asks this every couple of seconds. It answers with the
    submission's own state only - never with anything about other students.
    """
    lesson = get_object_or_404(Class, id=lesson_id, group_id=group_id)

    if not Member.objects.filter(user=request.user, group=lesson.group).exists():
        raise Http404

    assignment = get_object_or_404(
        Assignment,
        student=request.user,
        session=lesson,
        mode=Assignment.Mode.CLASS,
    )

    submission = get_object_or_404(Submission, assignment=assignment)

    waiting = _queue_state(submission)

    # Ha már nincs mire várni, a lap ide megy tovább. A sikertelen értékelés is
    # ide tartozik: azt az eredménylap magyarázza el, a visszaúttal együtt.
    if waiting is None and submission.state in (
        Submission.State.GRADED,
        Submission.State.FAILED,
    ):
        next_url = reverse("evaluation", kwargs={"group_id": group_id, "lesson_id": lesson_id})
    elif waiting is None:
        next_url = reverse("ocr_recognition", kwargs={"group_id": group_id, "lesson_id": lesson_id})
    else:
        next_url = ""

    return JsonResponse(
        {
            "state": submission.state,
            "waiting": waiting is not None,
            "kind": waiting["kind"] if waiting else "",
            "position": waiting["position"] if waiting else 0,
            "wait_seconds": waiting["wait_seconds"] if waiting else 0,
            "workers": queue.workers(),
            "next_url": next_url,
        }
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

            return redirect(
            "evaluation",
            group_id=group_id,
            lesson_id=lesson_id,
            )

        started = _start_evaluation(request, submission, ocr_attempt)

        return redirect(
            "ocr_recognition" if started else "evaluation",
            group_id=group_id,
            lesson_id=lesson_id,
        )

    latest = submission.evaluations.first()

    has_result = latest is not None and latest.final_score is not None

    return render(
        request,
        "evaluation.html",
        {
            "lesson": lesson,
            "group": lesson.group,
            "course": lesson.group.course,
            "assignment": assignment,
            "submission": submission,
            "ocr_attempt": ocr_attempt,
            "evaluation": latest if has_result else None,
            "failed": not has_result and submission.state == Submission.State.FAILED,
            "queued": _queue_state(submission),
            "lesson_number": lesson.position,
        },
    )


def _start_evaluation(request, submission, ocr_attempt):
    """Put the evaluation in the queue, unless this submission is already graded.

    Returns True when a job is waiting, so the caller knows whether to send
    the student to the waiting page or back to the result.
    """
    if submission.state == Submission.State.GRADED:
        messages.error(request, "This submission has already been evaluated.")
        return

    if "student_note" in request.POST:
        submission.student_note = request.POST.get("student_note", "").strip()
        submission.save(update_fields=["student_note"])

    logger.info(
        "Evaluation requested: user=%s submission=%s note_length=%s",
        request.user.id,
        submission.id,
        len(submission.student_note),
    )

    Submission.objects.filter(pk=submission.pk).update(state=Submission.State.GRADING)
    submission.refresh_from_db(fields=["state"])

    job = queue.enqueue(submission, Job.Kind.GRADING)

    logger.info(
        "Evaluation queued: user=%s submission=%s job=%s",
        request.user.id,
        submission.id,
        job.id,
    )

    return True


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
