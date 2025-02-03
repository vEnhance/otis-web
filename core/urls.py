from django.urls import path
from django.views.generic.base import RedirectView

from . import views

urlpatterns = [
    path(
        r"synopsis/",  # legacy URL
        RedirectView.as_view(pattern_name="catalog", permanent=True),
    ),
    path(r"catalog/", views.UnitGroupListView.as_view(), name="catalog"),
    path(r"catalog/public/", views.PublicCatalog.as_view(), name="catalog-public"),
    path(r"gallery/", views.UnitArtworkListView.as_view(), name="artwork-list"),
    path(r"unit-list/", views.SortedUnitListView.as_view(), name="sorted-unit-list"),
    path(
        r"admin-unit-list/", views.AdminUnitListView.as_view(), name="admin-unit-list"
    ),
    path(r"prefs/", views.UserProfileUpdateView.as_view(), name="profile"),
    path(r"unit/problems/<int:pk>/", views.unit_problems, name="view-problems"),
    path(r"unit/tex/<int:pk>/", views.unit_tex, name="view-tex"),
    path(r"unit/solutions/<int:pk>/", views.unit_solutions, name="view-solutions"),
    path(r"dismiss/news/", views.dismiss, name="dismiss-news"),
]
