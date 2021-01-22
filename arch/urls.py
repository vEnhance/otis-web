from django.urls import path

from . import views

urlpatterns = [
	path(r'problem/<int:group>/', views.ProblemList.as_view(), name='problem_list'),
	path(r'problem/<int:group>/create/', views.ProblemCreate.as_view(), name='problem_create'),
	path(r'problem/update/<int:pk>/', views.ProblemUpdate.as_view(), name='problem_update'),
	path(r'problem/delete/<int:pk>/', views.ProblemDelete.as_view(), name='problem_delete'),
	path(r'hint/view/<int:pk>/', views.HintDetail.as_view(), name='hint_detail'),
	path(r'hints/<int:problem>/', views.HintList.as_view(), name='hint_list'),
	path(r'hints/<int:problem>/create', views.HintCreate.as_view(), name='hint_create'),
	path(r'hint/update/<int:pk>/', views.HintUpdate.as_view(), name='hint_update'),
	path(r'hint/delete/<int:pk>/', views.HintDelete.as_view(), name='hint_delete'),
	]
