from django.conf.urls import url

from . import views

urlpatterns = [
	url(r'curriculum/([0-9]+)/$', views.curriculum, name='curriculum'),
]
