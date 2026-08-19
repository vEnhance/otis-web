from django.urls import path

from . import views

urlpatterns = [
    path(r"", views.YearbookIndex.as_view(), name="yearbook-index"),
    path(r"list/", views.YearbookList.as_view(), name="yearbook-list"),
    path(r"create/", views.YearbookCreate.as_view(), name="yearbook-create"),
    path(r"edit/", views.YearbookUpdate.as_view(), name="yearbook-update"),
    path(r"page/<int:pk>/", views.YearbookDetail.as_view(), name="yearbook-detail"),
]
