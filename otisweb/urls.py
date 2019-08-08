"""otisweb URL Configuration"""

from django.urls import include
from django.conf.urls import url
from django.conf.urls.static import static
from django.contrib import admin, auth
from django.views.generic import RedirectView

from . import settings
from django.views.generic.base import TemplateView
from .forms import ExtendedUserRegistrationForm
from .views import EditedRegistrationView

urlpatterns = [
	url(r'^admin/', admin.site.urls),
	url(r'^dash/', include('dashboard.urls')),
	url(r'^roster/', include('roster.urls')),
	url(r'^core/', include('core.urls')),
	url(r'^hijack/', include('hijack.urls')),
	url(r'^accounts/', include('django.contrib.auth.urls')),
	url(r'^register/$',
		EditedRegistrationView.as_view(form_class=ExtendedUserRegistrationForm),
		name='registration_register'),
	url(r'^register/closed/$', TemplateView.as_view(
		template_name="registration/registration_closed.html"
		), name='registration_disallowed'),
	url(r'^$', RedirectView.as_view(pattern_name='index')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = 'OTIS-WEB Administrative Control Panel'
admin.site.index_title = 'Dashboard'
admin.site.site_title  = 'OTIS-WEB Admin'
