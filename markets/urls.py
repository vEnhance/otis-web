from django.urls import path

from . import views

urlpatterns = [
	path(r'guess/<str:slug>/', views.SubmitGuess.as_view(), name='market-guess'),
	path(r'results/<str:slug>/', views.MarketResults.as_view(), name='market-results'),
	path(r'list/', views.MarketList.as_view(), name='market-list'),
	path(r'list/past/', views.MarketListPast.as_view(), name='market-list-past'),
	path(r'pending/<int:pk>/', views.GuessView.as_view(), name='market-pending'),
	path(r'recompute/<str:slug>/', views.recompute, name='market-recompute'),
]
