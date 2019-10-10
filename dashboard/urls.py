from django.conf.urls import url

from . import views

urlpatterns = [
	url(r'portal/([0-9]+)/$', views.portal, name='portal'),
	url(r'uploads/([0-9]+)/([0-9]+)/$', views.uploads, name='uploads'),
	url(r'editfile/(?P<pk>[0-9]+)/$', views.UpdateFile.as_view(), name='editfile'),
	url(r'deletefile/(?P<pk>[0-9]+)/$', views.DeleteFile.as_view(), name='delfile'),
	url(r'quasigrader/([0-9]+)/$', views.quasigrader, name='quasigrader'),
	url(r'idlewarn/$', views.idlewarn, name='idlewarn'),
	url(r'past/$', views.past, name='past'),
	url(r'index/$', views.index, name='index'),
]
