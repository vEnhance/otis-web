from django.urls import path

from . import views
from django.views.generic.base import RedirectView

urlpatterns = [
	path(r'create/', views.ProblemCreate.as_view(), name='problem-create'),
	path(r'<str:puid>/edit', views.ProblemUpdate.as_view(), name='problem-update'),
	path(r'<str:puid>/delete', views.ProblemDelete.as_view(), name='problem-delete'),
	path(r'<str:puid>/<int:number>/', views.HintDetail.as_view(), name='hint-detail'),
	path(r'<str:puid>/', views.HintList.as_view(), name='hint-list'),
	path(r'<str:puid>/add', views.HintCreate.as_view(), name='hint-create'),
	path(r'<str:puid>/<int:number>/edit', views.HintUpdate.as_view(), name='hint-update'),
	path(r'<str:puid>/<int:number>/delete', views.HintDelete.as_view(), name='hint-delete'),
	path(r'', views.index, name='arch-index'),
	]
