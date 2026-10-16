from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from .views import evaluation, generate_assignment, generated_assignment, home, ocr_recognition, register, course_detail, leave_course, lesson_detail

urlpatterns = [
    path("",auth_views.LoginView.as_view(template_name="login.html", redirect_authenticated_user=True,), name="login"),
    path("home/", home, name="home"),
    path("home/evaluation/", evaluation, name="evaluation"),
    path("register/", register, name="register"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("course/<int:group_id>/", course_detail, name="course_detail"),
    path("course/<int:group_id>/leave/", leave_course, name="leave_course"),
    path("course/<int:group_id>/lesson/<int:lesson_id>/", lesson_detail, name="lesson_detail"),
    path("course/<int:group_id>/lesson/<int:lesson_id>/generate/", generate_assignment, name="generate_assignment"),
    path("course/<int:group_id>/lesson/<int:lesson_id>/assignment/", generated_assignment, name="generated_assignment"),
    path("course/<int:group_id>/lesson/<int:lesson_id>/recognition/", ocr_recognition, name="ocr_recognition"),
    path("admin/", admin.site.urls),
]

if settings.DEV_TOOLS_ENABLED:
    urlpatterns += [path("dev/", include("devtools.urls"))]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
