from django.urls import path

from . import views

urlpatterns = [
	path(r'guess/<str:slug>/', views.SubmitGuess.as_view(), name='market-guess'),
]
