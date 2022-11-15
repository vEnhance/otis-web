from django.urls import path

from . import views

urlpatterns = [
    path(r'new', views.ProblemSuggestionCreate.as_view(), name='suggest-new'),
    path(r'<int:unit_id>/new/', views.ProblemSuggestionCreate.as_view(), name='suggest-new'),
    path(r'<int:pk>/edit/', views.ProblemSuggestionUpdate.as_view(), name='suggest-update'),
    path(r'list/', views.ProblemSuggestionList.as_view(), name='suggest-list'),
]
