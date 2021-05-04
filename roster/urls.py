from django.urls import path

from . import views

urlpatterns = [
	path(r'curriculum/<int:student_id>/', views.curriculum, name='currshow'),
	path(r'finalize/<int:student_id>/', views.finalize, name='finalize'),
	path(r'advance/<int:student_id>/', views.advance, name='advance'),
	path(r'auto-advance/<int:student_id>/<int:unit_id>/', views.auto_advance, name='auto-advance'),
	path(r'auto-advance/<int:student_id>/<int:unit_id>/<int:target_id>/', views.auto_advance, name='auto-advance'),
	path(r'invoice/', views.invoice),
	path(r'invoice/<int:student_id>/', views.invoice, name='invoice'),
	path(r'invoice/<int:student_id>/<str:checksum>/', views.invoice_standalone, name='invoice-standalone'),
	path(r'master-schedule/', views.master_schedule, name='master-schedule'),
	path(r'edit-invoice/<int:pk>', views.UpdateInvoice.as_view(), name='edit-invoice'),
	path(r'inquiry/<int:student_id>', views.inquiry, name='inquiry'),
	path(r'inquiry/list/', views.ListInquiries.as_view(), name='list-inquiry'),
	path(r'inquiry/edit/<int:pk>/', views.EditInquiry.as_view(), name='edit-inquiry'),
	path(r'inquiry/approve/<int:pk>/', views.approve_inquiry, name='approve-inquiry'),
	path(r'inquiry/approve/all/', views.approve_inquiry_all, name='approve-inquiry-all'),
	path(r'delinquent/<int:student_id>/', views.delinquent, name='delinquent'),
]
