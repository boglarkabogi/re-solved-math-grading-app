from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from .views import evaluation, generated_assignment, home, ocr_recognition

urlpatterns = [
    path("", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("home/", home, name="home"),
    path("home/generated/", generated_assignment, name="generated_assignment"),
    path("home/recognition/", ocr_recognition, name="ocr_recognition"),
    path("home/evaluation/", evaluation, name="evaluation"),
    path("kilepes/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
    path("beadas/", include("submissions.urls")),
]

if settings.DEV_TOOLS_ENABLED:
    urlpatterns += [path("dev/", include("devtools.urls"))]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
