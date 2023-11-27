from django.urls import path

from . import views

urlpatterns = [
    path(r"list/", views.TubeList.as_view(), name="tubes-list"),
    path(r"invite/<int:pk>/", views.tube_join, name="tubes-join"),
]
