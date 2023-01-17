from django.urls import path

from . import views

urlpatterns = [
    path(r"new/", views.ProblemSuggestionCreate.as_view(), name="suggest-new"),
    path(
        r"new/<int:unit_pk>",
        views.ProblemSuggestionCreate.as_view(),
        name="suggest-new",
    ),
    path(r"<int:pk>/", views.ProblemSuggestionUpdate.as_view(), name="suggest-update"),
    path(r"list/", views.ProblemSuggestionList.as_view(), name="suggest-list"),
    path(r"queue/", views.SuggestionQueueList.as_view(), name="suggestion-queue-listing")
]
