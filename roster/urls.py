from django.conf.urls import url

from . import views

urlpatterns = [
	url(r'curriculum/([0-9]+)/$', views.curriculum, name='currshow'),
	url(r'advance/([0-9]+)/$', views.advance, name='advance'),
	url(r'invoice/$', views.invoice),
	url(r'invoice/([0-9]+)/$', views.invoice, name='invoice'),
	url(r'master-schedule/$', views.master_schedule, name='master-schedule'),
	url(r'edit-invoice/(?P<pk>[0-9]+)$', views.UpdateInvoice.as_view(), name='edit-invoice'),
]
