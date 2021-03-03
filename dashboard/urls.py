from django.urls import path

from . import views

urlpatterns = [
	path(r'portal/<int:student_id>/', views.portal, name='portal'),
	path(r'uploads/<int:student_id>/<int:unit_id>/', views.uploads, name='uploads'),
	path(r'editfile/<int:pk>/', views.UpdateFile.as_view(), name='editfile'),
	path(r'deletefile/<int:pk>/', views.DeleteFile.as_view(), name='delfile'),
	path(r'quasigrader/', views.quasigrader, name='quasigrader'),
	path(r'quasigrader/<int:num_hours>/', views.quasigrader, name='quasigrader'),
	path(r'idlewarn/', views.idlewarn, name='idlewarn'),
	path(r'leaderboard/', views.leaderboard, name='leaderboard'),
	path(r'downloads/<int:pk>/', views.DownloadListView.as_view(), name='downloads'),
	path(r'past/', views.past, name='past'),
	path(r'index/', views.index, name='index'),
	path(r'suggest/<int:student_id>/<int:unit_id>/new', views.ProblemSuggestionCreate.as_view(), name='suggest_new'),
	path(r'suggest/<int:pk>/edit', views.ProblemSuggestionUpdate.as_view(), name='suggest_update'),
	path(r'suggest/<int:student_id>/list', views.ProblemSuggestionList.as_view(), name='suggest_list'),
	path(r'suggest/resolve/', views.pending_contributions, name='pending_suggest'),
	path(r'suggest/resolve/<int:suggestion_id>', views.pending_contributions, name='resolve_suggest'),
]
