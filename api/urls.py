from django.urls import path

from . import views

urlpatterns = [
    path("sessions/", views.create_session, name="session-create"),
    path(
        "sessions/<uuid:session_id>/",
        views.session_detail,
        name="session-detail",
    ),
]
