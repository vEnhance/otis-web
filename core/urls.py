from django.urls import path

from . import views

urlpatterns = [
	path(r'classroom/', views.classroom, name='classroom'),
	path(r'synopsis/', views.UnitGroupListView.as_view(), name='synopsis'),
	path(r'unit/problems/<int:pk>/', views.unit_problems, name='view-problems'),
	path(r'unit/tex/<int:pk>/', views.unit_tex, name='view-tex'),
	path(r'unit/solutions/<int:pk>/', views.unit_solutions,
				name='view-solutions'),
]
