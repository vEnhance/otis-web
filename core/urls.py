from django.conf.urls import url

from . import views

urlpatterns = [
	url(r'synopsis/$', views.UnitGroupListView.as_view(), name='synopsis'),
	url(r'unit/p/(?P<pk>[0-9]+)/(?P<hash>[0-9a-z]+)$', views.unit_problems, name='view_problems'),
	url(r'unit/s/(?P<pk>[0-9]+)/(?P<hash>[0-9a-z]+)$', views.unit_solutions, name='view_solutions'),
]
