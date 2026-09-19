from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from .views import kezdolap

urlpatterns = [
    path("", kezdolap, name="kezdolap"),
    path("belepes/", auth_views.LoginView.as_view(template_name="belepes.html"), name="login"),
    path("kilepes/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
    path("beadas/", include("submissions.urls")),
]

if settings.DEV_TOOLS_ENABLED:
    urlpatterns += [path("dev/", include("devtools.urls"))]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
