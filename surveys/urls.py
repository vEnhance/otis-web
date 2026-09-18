from django.urls import path

from . import views

urlpatterns = [
    path(r"<int:survey_pk>/", views.survey_detail, name="survey-detail"),
    path(r"<int:survey_pk>/submit/", views.survey_submit, name="survey-submit"),
    path(
        r"<int:survey_pk>/feedback/<uuid:token>/",
        views.gm_feedback_detail,
        name="survey-gm-feedback",
    ),
    path(r"", views.survey_list, name="survey-list"),
]
