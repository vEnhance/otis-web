from django.urls import path

from . import views

urlpatterns = [
    path(r"stats/<int:student_pk>/", views.stats, name="stats"),
    path(
        r"achievements/", views.AchievementList.as_view(), name="achievements-listing"
    ),
    path(
        r"achievements/<int:pk>/<str:checksum>/",
        views.AchievementCertifyList.as_view(),
        name="achievements-certify",
    ),
    path(r"foundlist/<int:pk>/", views.FoundList.as_view(), name="found-listing"),
    path(
        r"solution/<int:pk>/",
        views.AchievementDetail.as_view(),
        name="diamond-solution",
    ),
    path(r"leaderboard/", views.leaderboard, name="leaderboard"),
    path(r"palace/<int:student_pk>/", views.PalaceList.as_view(), name="palace-list"),
    path(r"palace/evan/", views.AdminPalaceList.as_view(), name="admin-palace-list"),
    path(
        r"carve/<int:student_pk>/", views.PalaceUpdate.as_view(), name="palace-update"
    ),
    path(
        r"forge/<int:student_pk>/", views.DiamondUpdate.as_view(), name="diamond-update"
    ),
]
