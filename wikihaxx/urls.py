from django.urls.conf import path

from . import views

urlpatterns = [
	path(r'problem/<str:puid>/', views.problem, name='wiki-problem'),
	path(r'unitgroup/<int:pk>/', views.unitgroup, name='wiki-unitgroup'),
]
