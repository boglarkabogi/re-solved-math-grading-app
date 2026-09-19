from django.urls import path

from . import views

app_name = "submissions"

urlpatterns = [
    path("", views.sajat_beadasok, name="sajat_beadasok"),
]
