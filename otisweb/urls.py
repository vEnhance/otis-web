"""otisweb URL Configuration"""

from django.urls import include
from django.conf.urls import url
from django.conf.urls.static import static
from django.contrib import admin, auth
from django.views.generic import RedirectView

from . import settings
from django.views.generic.base import TemplateView
from .forms import OTISUserRegistrationForm
from .views import OTISRegistrationView

urlpatterns = [
	url(r'^admin/', admin.site.urls),
	url(r'^dash/', include('dashboard.urls')),
	url(r'^roster/', include('roster.urls')),
	url(r'^core/', include('core.urls')),
	url(r'^hijack/', include('hijack.urls')),
	url(r'^accounts/', include('django.contrib.auth.urls')),
	url(r'^register/$',
		OTISRegistrationView.as_view(form_class=OTISUserRegistrationForm),
		name='django_registration_register'),
	url(r'^register/closed/$', TemplateView.as_view(
		template_name="django_registration/registration_closed.html"
		), name='django_registration_disallowed'),
	url(r'^register/complete/$',
		RedirectView.as_view(pattern_name='index'),
		name='django_registration_complete'),
	url(r'^$', RedirectView.as_view(pattern_name='index')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = 'OTIS-WEB Admin Control Panel'
admin.site.index_title = 'Dashboard'
admin.site.site_title  = 'OTIS-WEB Admin'
