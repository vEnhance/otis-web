from django.urls import path
from . import views

urlpatterns = [
	path(r'invoice/<int:student_id>/<str:checksum>/', views.invoice, name='payments-invoice'),
	path(r'config/', views.config, name='payments-config'),
	path(r'checkout/<int:invoice_id>/<int:amount>/', views.checkout, name='payments-checkout'),
	path(r'success/', views.success, name='payments-success'),
	path(r'cancelled/', views.cancelled, name='payments-cancelled'),
	path(r'webhook/', views.webhook, name='payments-webhook'),
]
