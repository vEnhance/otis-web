from django.urls import path

from . import views

urlpatterns = [
	path(r'curriculum/<int:student_id>/', views.curriculum, name='currshow'),
	path(r'finalize/<int:student_id>/', views.finalize, name='finalize'),
	path(r'advance/<int:student_id>/', views.advance, name='advance'),
	path(r'invoice/', views.invoice, name='invoice'),
	path(r'invoice/<int:student_id>/', views.invoice, name='invoice'),
	path(r'master-schedule/', views.master_schedule, name='master-schedule'),
	path(r'edit-invoice/<int:pk>/', views.UpdateInvoice.as_view(), name='edit-invoice'),
	path(r'inquiry/<int:student_id>/', views.inquiry, name='inquiry'),
	path(r'register/', views.register, name='register'),
	path(r'profile/', views.update_profile, name='update-profile'),
	path(r'spreadsheet/', views.spreadsheet, name='admin-spreadsheet'),
	path(r'mystery_unlock/easier/', views.unlock_rest_of_mystery, kwargs={'delta': 1}),
	path(r'mystery_unlock/harder/', views.unlock_rest_of_mystery, kwargs={'delta': 2}),
]
