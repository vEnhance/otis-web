from django.urls import path

from . import views

urlpatterns = [
    path(
        r"invoice/<int:student_pk>/<str:checksum>/",
        views.invoice,
        name="payments-invoice",
    ),
    path(r"config/", views.config, name="payments-config"),
    path(
        r"checkout/<int:invoice_pk>/<int:amount>/",
        views.checkout,
        name="payments-checkout",
    ),
    path(r"success/", views.success, name="payments-success"),
    path(r"cancelled/", views.cancelled, name="payments-cancelled"),
    path(r"webhook/", views.webhook, name="payments-webhook"),
    path(r"worker/view/", views.WorkerDetail.as_view(), name="worker-detail"),
    path(r"worker/update/", views.WorkerUpdate.as_view(), name="worker-update"),
    path(r"jobs/", views.JobFolderList.as_view(), name="job-index"),
    path(r"jobs/<str:slug>/", views.JobList.as_view(), name="job-list"),
    path(r"job/<int:pk>/", views.JobDetail.as_view(), name="job-detail"),
    path(r"job/claim/<int:pk>/", views.job_claim, name="job-claim"),
    path(r"job/submit/<int:pk>/", views.JobUpdate.as_view(), name="job-update"),
    path(
        r"inactive/<str:slug>/", views.InactiveWorkerList.as_view(), name="job-inactive"
    ),
]
