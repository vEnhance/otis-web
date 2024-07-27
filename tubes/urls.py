from django.urls import path

from . import views

urlpatterns = [
    path(r"list/", views.TubeList.as_view(), name="tube-list"),
    path(r"invite/<int:pk>/", views.tube_join, name="tube-join"),
]
