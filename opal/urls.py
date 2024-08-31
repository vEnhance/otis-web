from django.urls import path
from django.views.generic.base import RedirectView, TemplateView

from . import views

urlpatterns = [
    path(
        r"authors/",
        TemplateView.as_view(template_name="opal/instructions_authors.html"),
        name="opal-authors",
    ),
    path(
        r"rules/",
        TemplateView.as_view(template_name="opal/instructions_solvers.html"),
        name="opal-rules",
    ),
    path(r"list/", views.HuntList.as_view(), name="opal-hunt-list"),
    path(r"puzzles/<str:slug>/", views.PuzzleList.as_view(), name="opal-puzzle-list"),
    path(r"leaderboard/<str:slug>/", views.leaderboard, name="opal-leaderboard"),
    path(
        r"puzzle/<str:hunt>/<str:slug>/",
        views.show_puzzle,
        name="opal-show-puzzle",
    ),
    path(
        r"finish/<str:hunt>/<str:slug>/",
        views.finish,
        name="opal-finish",
    ),
    path(
        r"guesses/<str:hunt>/<str:slug>/",
        views.AttemptsList.as_view(),
        name="opal-attempts-list",
    ),
    path(
        r"person/<str:slug>/<int:user_pk>/",
        views.person_log,
        name="opal-person-log",
    ),
    path(r"", RedirectView.as_view(pattern_name="opal-hunt-list"), name="opal-index"),
]
