from django.urls import path

from . import views

urlpatterns = [
	path(r'portal/<int:student_id>/', views.portal, name='portal'),
	path(r'uploads/<int:student_id>/<int:unit_id>/', views.uploads, name='uploads'),
	path(r'editfile/<int:pk>/', views.UpdateFile.as_view(), name='editfile'),
	path(r'deletefile/<int:pk>/', views.DeleteFile.as_view(), name='delfile'),
	path(r'quasigrader/<int:num_hours>/', views.quasigrader, name='quasigrader'),
	path(r'idlewarn/', views.idlewarn, name='idlewarn'),
	path(r'leaderboard/', views.leaderboard, name='leaderboard'),
	path(r'downloads/<int:pk>/', views.DownloadListView.as_view(), name='downloads'),
	path(r'past/', views.past, name='past'),
	path(r'index/', views.index, name='index'),
]
