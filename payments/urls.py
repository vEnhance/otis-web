from django.urls import path
from . import views

urlpatterns = [
    path(r'invoice/<int:student_id>/<str:checksum>/', views.invoice, name='payments-invoice'),
    path(r'config/', views.config, name='payments-config'),
    path(r'checkout/<int:invoice_id>/<int:amount>/', views.checkout, name='payments-checkout'),
    path(r'success/', views.success, name='payments-success'),
    path(r'cancelled/', views.cancelled, name='payments-cancelled'),
    path(r'webhook/', views.webhook, name='payments-webhook'),
    path(r'worker/view/', views.WorkerDetail.as_view(), name='worker-detail'),
    path(r'worker/update/', views.WorkerUpdate.as_view(), name='worker-update'),
    path(r'jobs/', views.JobFolderList.as_view(), name='job-index'),
    path(r'jobs/<str:slug>/', views.JobList.as_view(), name='job-list'),
]
