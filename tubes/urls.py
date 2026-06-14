from django.urls import path

from . import views

urlpatterns = [
    path(r"landing/", views.LandingView.as_view(), name="oime-landing"),
    path(r"proposals/", views.ProposalListView.as_view(), name="oime-proposal-list"),
    path(r"propose/", views.ProposalCreateView.as_view(), name="oime-proposal-create"),
    path(r"proposal/<int:pk>/", views.proposal_detail, name="oime-proposal-detail"),
    path(r"proposal/<int:pk>/begin/", views.proposal_start, name="oime-proposal-start"),
    path(
        r"proposal/<int:pk>/edit/",
        views.ProposalUpdateView.as_view(),
        name="oime-proposal-update",
    ),
    path(r"proposal/<int:pk>/fight/", views.proposal_fight, name="oime-proposal-fight"),
    path(r"proposal/<int:pk>/start/", views.start_attempt, name="oime-start-attempt"),
    path(r"proposal/<int:pk>/submit/", views.submit_answer, name="oime-submit-answer"),
    path(r"proposal/<int:pk>/giveup/", views.give_up, name="oime-give-up"),
    path(r"proposal/<int:pk>/upvote/", views.upvote_proposal, name="oime-upvote"),
    path(r"proposal/<int:pk>/reveal/", views.reveal_solution, name="oime-reveal"),
    path(
        r"proposal/<int:pk>/archive/",
        views.toggle_archive,
        name="oime-proposal-archive",
    ),
    path(
        r"proposal/<int:pk>/results/",
        views.proposal_results,
        name="oime-proposal-results",
    ),
    path(r"comment/<int:pk>/edit/", views.edit_comment, name="oime-comment-edit"),
    path(r"setup/", views.oime_setup, name="oime-setup"),
    path(r"casual/", views.go_casual, name="oime-casual"),
    path(r"serious/", views.go_serious, name="oime-serious"),
]
