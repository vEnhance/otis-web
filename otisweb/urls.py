"""otisweb URL Configuration"""

from django.urls import include, path
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic import RedirectView
from django.views.generic.base import TemplateView
import debug_toolbar

from . import settings
assert settings.MEDIA_URL is not None

urlpatterns = [
	path(r'admin/', admin.site.urls),
	path(r'arch/', include('arch.urls')),
	path(r'dash/', include('dashboard.urls')),
	path(r'roster/', include('roster.urls')),
	path(r'core/', include('core.urls')),
	path(r'hijack/', include('hijack.urls')),
	path(r'accounts/', include('allauth.urls')),
	path(r'__debug__/', include(debug_toolbar.urls)),
	path(r'robots.txt',
		TemplateView.as_view(template_name='robots.txt', content_type='text/plain'),
		),
	path(r'favicon.ico',
		RedirectView.as_view(url="https://web.evanchen.cc/icons/favicon.ico")
		),
	path(r'', RedirectView.as_view(pattern_name='index')),
	] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) # type: ignore

admin.site.site_header = 'OTIS-WEB Admin Control Panel'
admin.site.index_title = 'Dashboard'
admin.site.site_title  = 'OTIS-WEB Admin'
