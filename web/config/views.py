from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from django.contrib import messages

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
    return render(request, "home.html")

@login_required
def generated_assignment(request):
    attempt = int(request.GET.get("attempt", 1))

    return render(
        request,
        "generated_assignment.html",
        {
            "attempt": attempt,
        },
    )


@login_required
def ocr_recognition(request):
    attempt = int(request.GET.get("attempt", 1))

    # 1 és 3 között tartjuk
    attempt = max(1, min(attempt, 3))

    return render(
        request,
        "ocr_recognition.html",
        {
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
