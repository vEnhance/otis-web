from django.urls import path
from django.views.generic.base import RedirectView

from . import views

urlpatterns = [
    path(
        r"guess/<slug:market_slug>/", views.SubmitGuess.as_view(), name="market-guess"
    ),
    path(
        r"results/<slug:market_slug>/",
        views.MarketResults.as_view(),
        name="market-results",
    ),
    path(r"list/", views.MarketList.as_view(), name="market-list"),
    path(r"list/past/", views.MarketListPast.as_view(), name="market-list-past"),
    path(r"spades/", views.MarketSpades.as_view(), name="market-spades"),
    path(
        r"pending/<slug:market_slug>/", views.GuessView.as_view(), name="market-pending"
    ),
    path(r"recompute/<slug:market_slug>/", views.recompute, name="market-recompute"),
    path(
        r"", RedirectView.as_view(pattern_name="market-list"), name="market-recompute"
    ),
    path(r"new-market/", views.MarketCreateView.as_view(), name="market-new"),
]
