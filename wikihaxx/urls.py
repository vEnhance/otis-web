from django.urls.conf import path

from . import views

urlpatterns = [
	path(r'unitgroup/<int:pk>/', views.unitgroup, name='wiki-unitgroup'),
]
