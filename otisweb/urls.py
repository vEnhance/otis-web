"""otisweb URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""

from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin, auth
from django.views.generic import RedirectView

from registration.backends.simple.views import RegistrationView
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.db.utils import OperationalError
from . import settings
from django.views.generic.base import TemplateView

import core

class EditedRegistrationView(RegistrationView):
	def registration_allowed(self):
		try:
			semester = core.models.Semester.objects.get(active=True)
			return semester.registration_open
		except (MultipleObjectsReturned, ObjectDoesNotExist, OperationalError):
			return False

urlpatterns = [
	url(r'^admin/', include(admin.site.urls)),
	url(r'^dash/', include('dashboard.urls')),
	url(r'^roster/', include('roster.urls')),
	url(r'^core/', include('core.urls')),
	url(r'^hijack/', include('hijack.urls')),
	url(r'^accounts/', include('django.contrib.auth.urls')),
	url(r'^register/$', EditedRegistrationView.as_view(), name='registration_register'),
	url(r'^register/closed/$', TemplateView.as_view(
		template_name="registration/registration_closed.html"
		), name='registration_disallowed'),
	url(r'^_ah/health/', RedirectView.as_view(pattern_name='index')), # health checks
	url(r'^$', RedirectView.as_view(pattern_name='index')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = 'OTIS-WEB Administrative Control Panel'
admin.site.index_title = 'Dashboard'
admin.site.site_title  = 'OTIS-WEB Admin'
