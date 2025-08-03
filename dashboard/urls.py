from django.urls import path
from django.views.generic.base import RedirectView

from . import views

urlpatterns = [
    path(r"portal/<int:student_pk>/", views.portal, name="portal"),
    path(r"conquer/<int:student_pk>/", views.submit_pset, name="submit-pset"),
    path(r"reconquer/<int:pk>/", views.resubmit_pset, name="resubmit-pset"),
    path(r"queue/", views.PSetQueueList.as_view(), name="pset-queue-listing"),
    path(r"uploads/<int:student_pk>/<int:unit_pk>/", views.uploads, name="uploads"),
    path(r"editfile/<int:pk>/", views.UpdateFile.as_view(), name="edit-file"),
    path(r"deletefile/<int:pk>/", views.DeleteFile.as_view(), name="delete-file"),
    path(r"idlewarn/", views.idlewarn, name="idlewarn"),
    path(r"downloads/<int:pk>/", views.DownloadList.as_view(), name="downloads"),
    path(r"pset/<int:pk>/", views.PSetDetail.as_view(), name="pset"),
    path(
        r"sent/<int:student_pk>/",
        views.StudentPSetList.as_view(),
        name="student-pset-list",
    ),
    path(r"past/", views.past, name="past"),
    path(r"past/<int:semester_pk>/", views.past, name="past"),
    path(
        r"bonus/<int:student_pk>/",
        views.bonus_level_request,
        name="bonus-level-request",
    ),
    path(r"years/", views.SemesterList.as_view(), name="semester-list"),
    path(r"index/", views.index, name="index"),
    path(r"certify/", views.certify, name="certify"),
    path(r"certify/<int:student_pk>/", views.certify, name="certify"),
    path(r"certify/<int:student_pk>/<str:checksum>/", views.certify, name="certify"),
    path(r"announce/", views.AnnouncementList.as_view(), name="announcement-list"),
    path(
        r"announce/<slug:slug>/",
        views.AnnouncementDetail.as_view(),
        name="announcement-detail",
    ),
    path(r"", RedirectView.as_view(pattern_name="index")),
    path(r"newslist/", views.news_list, name="news-list"),
]
