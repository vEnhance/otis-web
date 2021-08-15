from django.urls import path

from . import views

urlpatterns = [
	path(r'portal/<int:student_id>/', views.portal, name='portal'),
	path(r'conquer/<int:student_id>/', views.submit_pset, name='submit-pset'),
	path(r'achievements/<int:student_id>/', views.achievements, name='achievements'),
	path(r'achievements/listing/', views.AchievementList.as_view(), name='achievements-listing'),
	path(r'foundlist/<int:pk>/', views.FoundList.as_view(), name='found-listing'),
	path(r'uploads/<int:student_id>/<int:unit_id>/', views.uploads, name='uploads'),
	path(r'editfile/<int:pk>/', views.UpdateFile.as_view(), name='editfile'),
	path(r'deletefile/<int:pk>/', views.DeleteFile.as_view(), name='delfile'),
	path(r'idlewarn/', views.idlewarn, name='idlewarn'),
	path(r'downloads/<int:pk>/', views.DownloadList.as_view(), name='downloads'),
	path(r'pset/<int:pk>/', views.PSetDetail.as_view(), name='pset'),
	path(r'past/', views.past, name='past'),
	path(r'past/<int:semester>/', views.past, name='past'),
	path(r'index/', views.index, name='index'),
	path(r'suggest/<int:student_id>/new/', views.ProblemSuggestionCreate.as_view(), name='suggest-new'),
	path(r'suggest/<int:student_id>/<int:unit_id>/new/', views.ProblemSuggestionCreate.as_view(), name='suggest-new'),
	path(r'suggest/<int:pk>/edit/', views.ProblemSuggestionUpdate.as_view(), name='suggest-update'),
	path(r'suggest/<int:student_id>/list/', views.ProblemSuggestionList.as_view(), name='suggest-list'),
	path(r'suggest/resolve/', views.pending_contributions, name='pending-suggest'),
	path(r'suggest/resolve/<int:suggestion_id>/', views.pending_contributions, name='resolve-suggest'),
	path(r'leaderboard/', views.leaderboard, name='leaderboard'),
	path(r'api/', views.api, name='resolve-suggest'),
]
