from django.urls import path

from . import views

urlpatterns = [
	path(r'synopsis/', views.UnitGroupListView.as_view(), name='synopsis'),
	path(r'prefs/', views.UserProfileUpdateView.as_view(), name='profile'),
	path(r'unit/problems/<int:pk>/', views.unit_problems, name='view-problems'),
	path(r'unit/tex/<int:pk>/', views.unit_tex, name='view-tex'),
	path(r'unit/solutions/<int:pk>/', views.unit_solutions, name='view-solutions'),
	path(r'dismiss/email/', views.dismiss_emails, name='dismiss-emails'),
	path(r'dismiss/downloads/', views.dismiss_downloads, name='dismiss-downloads'),
]
