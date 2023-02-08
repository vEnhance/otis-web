from django.urls import path

from . import views

urlpatterns = [
    path(r"contests/", views.HanabiContestList.as_view(), name="hanabi-contests"),
    path(r"register/", views.HanabiPlayerCreateView.as_view(), name="hanabi-register"),
    path(r"results/<int:pk>/", views.HanabiReplayList.as_view(), name="hanabi-replays"),
    path(r"upload/<int:pk>/", views.hanabi_upload, name="hanabi-upload"),
]
