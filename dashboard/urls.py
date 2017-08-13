from django.conf.urls import url

from . import views

urlpatterns = [
	url(r'main/([0-9]+)/$', views.main, name='dashboard'),
	url(r'uploads/([0-9]+)/([0-9]+)/$', views.uploads, name='uploads'),
	url(r'editfile/(?P<pk>[0-9]+)/$', views.UpdateFile.as_view(), name='editfile'),
	url(r'deletefile/(?P<pk>[0-9]+)/$', views.DeleteFile.as_view(), name='delfile'),
	url(r'past/$', views.past, name='past'),
	url(r'index/$', views.index, name='index'),
]
