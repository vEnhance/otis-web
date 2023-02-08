from django.urls import path

from . import views

urlpatterns = [
    path(r"lookup/", views.lookup, name="arch-lookup"),
    path(r"pk/<int:pk>/", views.HintDetailByPK.as_view(), name="hint-detail-pk"),
    path(r"pk/<int:pk>/edit/", views.HintUpdateByPK.as_view(), name="hint-update-pk"),
    path(r"<str:puid>/edit/", views.ProblemUpdate.as_view(), name="problem-update"),
    path(r"<str:puid>/<int:number>/", views.HintDetail.as_view(), name="hint-detail"),
    path(r"<str:puid>/add/", views.HintCreate.as_view(), name="hint-create"),
    path(
        r"<str:puid>/<int:number>/edit/", views.HintUpdate.as_view(), name="hint-update"
    ),
    path(
        r"<str:puid>/<int:number>/delete/",
        views.HintDelete.as_view(),
        name="hint-delete",
    ),
    path(
        r"<str:puid>/",
        views.HintList.as_view(),
        name="hint-list",
        kwargs={"create_if_missing": False},
    ),
    path(
        r"<str:puid>/otis/",
        views.HintList.as_view(),
        name="hint-list",
        kwargs={"create_if_missing": True},
    ),
    path(r"<str:puid>/solution", views.view_solution, name="view-solution"),
    path(r"", views.ProblemCreate.as_view(), name="arch-index"),
    path(r"<str:puid>/vote/", views.VoteCreate.as_view(), name="vote-create"),
]
