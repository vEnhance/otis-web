from django.urls import path

from . import views

urlpatterns = [
    path(r'portal/<int:student_id>/', views.portal, name='portal'),
    path(r'conquer/<int:student_id>/', views.submit_pset, name='submit-pset'),
    path(r'reconquer/<int:pk>/', views.resubmit_pset, name='resubmit-pset'),
    path(r'queue/', views.PSetQueueList.as_view(), name='pset-queue-listing'),
    path(r'uploads/<int:student_id>/<int:unit_id>/', views.uploads, name='uploads'),
    path(r'editfile/<int:pk>/', views.UpdateFile.as_view(), name='editfile'),
    path(r'deletefile/<int:pk>/', views.DeleteFile.as_view(), name='delfile'),
    path(r'idlewarn/', views.idlewarn, name='idlewarn'),
    path(r'downloads/<int:pk>/', views.DownloadList.as_view(), name='downloads'),
    path(r'pset/<int:pk>/', views.PSetDetail.as_view(), name='pset'),
    path(r'sent/<int:student_id>/', views.StudentPSetList.as_view(), name='student-pset-list'),
    path(r'past/', views.past, name='past'),
    path(r'past/<int:semester_id>/', views.past, name='past'),
    path(r'years/', views.SemesterList.as_view(), name='semlist'),
    path(r'index/', views.index, name='index'),
    path(r'certify/', views.certify, name='certify'),
    path(r'certify/<int:student_id>/', views.certify, name='certify'),
    path(r'certify/<int:student_id>/<str:checksum>/', views.certify, name='certify'),
]
