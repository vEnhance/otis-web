from django.urls import path

from . import views

urlpatterns = [
	path(r'synopsis/', views.UnitGroupListView.as_view(), name='synopsis'),
	path(r'unit/p/<int:pk>/<str:hash>/', views.unit_problems, name='view-problems'),
	path(r'unit/s/<int:pk>/<str:hash>/', views.unit_solutions, name='view-solutions'),
]
