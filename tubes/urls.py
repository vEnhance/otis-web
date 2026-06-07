from django.urls import path

from . import views

urlpatterns = [
    path(r"list/", views.TubeList.as_view(), name="tube-list"),
    path(r"invite/<int:pk>/", views.tube_join, name="tube-join"),
    path(r"proposals/", views.ProposalListView.as_view(), name="oime-proposal-list"),
    path(r"propose/", views.ProposalCreateView.as_view(), name="oime-proposal-create"),
    path(r"proposal/<int:pk>/", views.proposal_detail, name="oime-proposal-detail"),
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
    path(r"comment/<int:pk>/edit/", views.edit_comment, name="oime-comment-edit"),
    path(r"setup/", views.oime_setup, name="oime-setup"),
]
