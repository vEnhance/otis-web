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
    path(
        r"<int:survey_pk>/inbox/",
        views.GMFeedbackInbox.as_view(),
        name="survey-gm-feedback-inbox",
    ),
    path(
        r"<int:survey_pk>/inbox/<int:feedback_pk>/",
        views.gm_feedback_respond,
        name="survey-gm-feedback-respond",
    ),
    path(
        r"<int:survey_pk>/comments/",
        views.InstructorCommentInbox.as_view(),
        name="survey-instructor-comment-inbox",
    ),
    path(
        r"<int:survey_pk>/comments/<int:comment_pk>/",
        views.instructor_comment_mark,
        name="survey-instructor-comment-mark",
    ),
    path(r"", views.survey_list, name="survey-list"),
]
