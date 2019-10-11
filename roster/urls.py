from django.conf.urls import url

from . import views

urlpatterns = [
	url(r'curriculum/([0-9]+)/$', views.curriculum, name='currshow'),
	url(r'advance/([0-9]+)/$', views.advance, name='advance'),
	url(r'invoice/$', views.invoice),
	url(r'invoice/([0-9]+)/$', views.invoice, name='invoice'),
	url(r'master-schedule/$', views.master_schedule, name='master-schedule'),
	url(r'edit-invoice/(?P<pk>[0-9]+)$', views.UpdateInvoice.as_view(), name='edit-invoice'),
	url(r'inquiry/([0-9]+)$', views.inquiry, name='inquiry'),
	url(r'inquiry/list/$', views.ListOpenInquiries.as_view(), name='list-inquiry'),
	url(r'inquiry/edit/(?P<pk>[0-9]+)/$', views.EditInquiry.as_view(), name='edit-inquiry'),
	url(r'inquiry/approve/(?P<pk>[0-9]+)/$', views.approve_inquiry, name='approve-inquiry'),
	url(r'inquiry/approve/all/$', views.approve_inquiry_all, name='approve-inquiry-all'),
]
