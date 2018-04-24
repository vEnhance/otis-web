from django.conf.urls import url

from . import views

urlpatterns = [
	url(r'synopsis/$', views.UnitGroupListView.as_view(), name='synopsis'),
]
