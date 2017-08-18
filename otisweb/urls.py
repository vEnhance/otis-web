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
from django.contrib import admin
from django.views.generic import RedirectView
from . import settings

urlpatterns = [
	url(r'^admin/', admin.site.urls),
	url(r'^dash/', include('dashboard.urls')),
	url(r'^roster/', include('roster.urls')),
	url(r'^hijack/', include('hijack.urls')),
	url(r'^accounts/', include('registration.backends.simple.urls')),
	url(r'^_ah/health/', RedirectView.as_view(pattern_name='index')), # health checks
	url(r'^$', RedirectView.as_view(pattern_name='index')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = 'OTIS-WEB Administrative Control Panel'
admin.site.index_title = 'Dashboard'
admin.site.site_title  = 'OTIS-WEB Admin'
