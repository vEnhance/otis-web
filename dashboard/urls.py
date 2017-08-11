from django.conf.urls import url

from . import views

urlpatterns = [
	url(r'main/([0-9]+)/$', views.main, name='dashboard'),
	url(r'uploads/([0-9]+)/$', views.uploads, name='uploads'),
]
