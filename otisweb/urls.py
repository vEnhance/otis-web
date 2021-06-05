"""otisweb URL Configuration"""

from django.urls import include, path
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic import RedirectView

from . import settings
from django.views.generic.base import TemplateView
from .forms import OTISUserRegistrationForm
from .views import OTISRegistrationView
assert settings.MEDIA_URL is not None

urlpatterns = [
	path(r'admin/', admin.site.urls),
	path(r'arch/', include('arch.urls')),
	path(r'dash/', include('dashboard.urls')),
	path(r'roster/', include('roster.urls')),
	path(r'core/', include('core.urls')),
	path(r'hijack/', include('hijack.urls')),
	path(r'accounts/', include('django.contrib.auth.urls')),
	path(r'register/',
		OTISRegistrationView.as_view(form_class=OTISUserRegistrationForm),
		name='django_registration_register'),
	path(r'register/closed/', TemplateView.as_view(
		template_name="django_registration/registration_closed.html"
		), name='django_registration_disallowed'),
	path(r'register/complete/',
		RedirectView.as_view(pattern_name='index'),
		name='django_registration_complete'),
	path(r'favicon.ico',
		RedirectView.as_view(url="https://web.evanchen.cc/icons/favicon.ico")
		),
	path(r'', RedirectView.as_view(pattern_name='index')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = 'OTIS-WEB Admin Control Panel'
admin.site.index_title = 'Dashboard'
admin.site.site_title  = 'OTIS-WEB Admin'
