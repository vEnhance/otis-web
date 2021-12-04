from django.urls import path

from . import views

urlpatterns = [
	path(r'score/', views.usemo_score, name='usemo-score'),
	path(r'grader/', views.usemo_grader, name='usemo-grader'),
]
