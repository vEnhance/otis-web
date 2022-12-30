from django.urls import path

from . import views

urlpatterns = [
    path(r"pdf/<int:pk>/", views.pdf, name="exam-pdf"),
    path(r"quiz/<int:student_pk>/<int:pk>", views.quiz, name="quiz"),
    path(r"mocks/", views.mocks, name="mocks"),
    path(r"mocks/<int:student_pk>/", views.mocks, name="mocks"),
    path(r"spades/", views.participation_points, name="participation-points"),
]
