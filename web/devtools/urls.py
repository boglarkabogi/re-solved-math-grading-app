from django.urls import path

from . import views

app_name = "devtools"

urlpatterns = [
    path("", views.proba, name="proba"),
]
