from django.conf.urls import url

from . import views

urlpatterns = [
	url(r'curriculum/([0-9]+)/$', views.curriculum, name='currshow'),
	url(r'advance/([0-9]+)/$', views.advance, name='advance'),
	url(r'master-schedule/$', views.master_schedule, name='master_schedule'),
]
