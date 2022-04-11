from django.urls import path

from . import views

urlpatterns = [
	path(r'portal/<int:student_id>/', views.portal, name='portal'),
	path(r'conquer/<int:student_id>/', views.submit_pset, name='submit-pset'),
	path(r'reconquer/<int:pk>/', views.resubmit_pset, name='resubmit-pset'),
	path(r'stats/<int:student_id>/', views.stats, name='stats'),
	path(r'achievements/', views.AchievementList.as_view(), name='achievements-listing'),
	path(r'foundlist/<int:pk>/', views.FoundList.as_view(), name='found-listing'),
	path(r'uploads/<int:student_id>/<int:unit_id>/', views.uploads, name='uploads'),
	path(r'editfile/<int:pk>/', views.UpdateFile.as_view(), name='editfile'),
	path(r'deletefile/<int:pk>/', views.DeleteFile.as_view(), name='delfile'),
	path(r'idlewarn/', views.idlewarn, name='idlewarn'),
	path(r'downloads/<int:pk>/', views.DownloadList.as_view(), name='downloads'),
	path(r'pset/<int:pk>/', views.PSetDetail.as_view(), name='pset'),
	path(r'past/', views.past, name='past'),
	path(r'past/<int:semester_id>/', views.past, name='past'),
	path(r'years/', views.SemesterList.as_view(), name='semlist'),
	path(r'index/', views.index, name='index'),
	path(r'suggest/new', views.ProblemSuggestionCreate.as_view(), name='suggest-new'),
	path(
		r'suggest/<int:unit_id>/new/', views.ProblemSuggestionCreate.as_view(), name='suggest-new'
	),
	path(
		r'suggest/<int:pk>/edit/', views.ProblemSuggestionUpdate.as_view(), name='suggest-update'
	),
	path(r'suggest/list/', views.ProblemSuggestionList.as_view(), name='suggest-list'),
	path(r'leaderboard/', views.leaderboard, name='leaderboard'),
	path(r'palace/<int:student_id>/', views.PalaceList.as_view(), name='palace-list'),
	path(r'palace/evan/', views.AdminPalaceList.as_view(), name='admin-palace-list'),
	path(r'carve/<int:student_id>/', views.PalaceUpdate.as_view(), name='palace-update'),
	path(r'forge/<int:student_id>/', views.DiamondUpdate.as_view(), name='diamond-update'),
	path(r'certify/<int:student_id>/', views.certify, name='certify'),
	path(r'certify/<int:student_id>/<str:checksum>/', views.certify, name='certify'),
]
