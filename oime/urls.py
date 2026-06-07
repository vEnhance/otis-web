from django.urls import path

from . import views

urlpatterns = [
    path(r"", views.ProposalListView.as_view(), name="oime-proposal-list"),
    path(r"propose/", views.ProposalCreateView.as_view(), name="oime-proposal-create"),
    path(r"proposal/<int:pk>/", views.proposal_detail, name="oime-proposal-detail"),
    path(r"proposal/<int:pk>/edit/", views.ProposalUpdateView.as_view(), name="oime-proposal-update"),
    path(r"proposal/<int:pk>/start/", views.start_attempt, name="oime-start-attempt"),
    path(r"proposal/<int:pk>/submit/", views.submit_answer, name="oime-submit-answer"),
    path(r"proposal/<int:pk>/giveup/", views.give_up, name="oime-give-up"),
    path(r"role/", views.role_select, name="oime-role-select"),
]
