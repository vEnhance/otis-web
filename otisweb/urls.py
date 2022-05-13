"""otisweb URL Configuration"""

import debug_toolbar
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django.views.generic.base import TemplateView

from . import settings

assert settings.MEDIA_URL is not None

urlpatterns = [
	path(r'admin/', admin.site.urls),
	path(r'aincrad/', include('aincrad.urls')),
	path(r'arch/', include('arch.urls')),
	path(r'core/', include('core.urls')),
	path(r'dash/', include('dashboard.urls')),
	path(r'exams/', include('exams.urls')),
	path(r'markets/', include('markets.urls')),
	path(r'mouse/', include('mouse.urls')),
	path(r'roster/', include('roster.urls')),
	path(r'payments/', include('payments.urls')),
	path(r'hijack/', include('hijack.urls')),
	path(r'accounts/', include('allauth.urls')),
	path(r'notifications/', include('django_nyt.urls')),
	path(r'wiki/', include('wiki.urls')),
	path(r'fandom/', include('wikihaxx.urls')),
	path(r'__debug__/', include(debug_toolbar.urls)),
	path(
		r'robots.txt',
		TemplateView.as_view(template_name='robots.txt', content_type='text/plain'),
	),
	path(r'favicon.ico', RedirectView.as_view(url="https://web.evanchen.cc/icons/favicon.ico")),
	path(r'', RedirectView.as_view(pattern_name='index')),
] + static(
	settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
)  # type: ignore

if settings.DEBUG:
	admin.site.site_header = '127.0.0.1'
	admin.site.index_title = 'Switchboard'
	admin.site.site_title = 'otis@localhost'
else:
	admin.site.site_header = 'OTIS Headquarters'
	admin.site.index_title = 'GM Panel'
	admin.site.site_title = 'OTIS HQ'
