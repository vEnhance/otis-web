from django.conf.urls import url

from . import views

urlpatterns = [
	url(r'([0-9]+)/$', views.dashboard, name='dashboard'),
]
