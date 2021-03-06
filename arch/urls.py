from django.urls import path

from . import views
from django.views.generic.base import RedirectView

urlpatterns = [
	path(r'problem/<int:group>/', views.ProblemList.as_view(), name='problem-list'),
	path(r'problem/<int:group>/create/', views.ProblemCreate.as_view(), name='problem-create'),
	path(r'problem/update/<int:pk>/', views.ProblemUpdate.as_view(), name='problem-update'),
	path(r'problem/delete/<int:pk>/', views.ProblemDelete.as_view(), name='problem-delete'),
	path(r'hint/view/<int:pk>/', views.HintDetail.as_view(), name='hint-detail'),
	path(r'hints/<int:problem>/', views.HintList.as_view(), name='hint-list'),
	path(r'hints/<int:problem>/create', views.HintCreate.as_view(), name='hint-create'),
	path(r'hint/update/<int:pk>/', views.HintUpdate.as_view(), name='hint-update'),
	path(r'hint/delete/<int:pk>/', views.HintDelete.as_view(), name='hint-delete'),
	path(r'', RedirectView.as_view(pattern_name='synopsis'), name='problem-list'),
	]
