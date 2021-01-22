from django.conf.urls import url

from . import views

urlpatterns = [
	url(r'problem/(?P<group>[0-9]+)/$', views.ListProblems.as_view(), name='list_problems'),
	url(r'problem/(?P<group>[0-9]+)/create$', views.CreateProblem.as_view(), name='create_problem'),
	url(r'problem/update/(?P<pk>[0-9]+)/$', views.UpdateProblem.as_view(), name='edit_problem'),
	url(r'problem/delete/(?P<pk>[0-9]+)/$', views.DeleteProblem.as_view(), name='delete_problem'),
	url(r'hint/(?P<problem>[0-9]+)/$', views.ListHints.as_view(), name='list_hints'),
	url(r'hint/(?P<problem>[0-9]+)/create$', views.CreateHint.as_view(), name='create_hint'),
	url(r'hint/update/(?P<pk>[0-9]+)/$', views.UpdateHint.as_view(), name='edit_hint'),
	url(r'hint/delete/(?P<pk>[0-9]+)/$', views.DeleteHint.as_view(), name='delete_hint'),
	]
