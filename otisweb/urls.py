"""otisweb URL Configuration"""

import debug_toolbar
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.generic.base import TemplateView

from . import settings

assert settings.MEDIA_URL is not None

# bots/scrapers hoping my website is made in WordPress should become
# more cultured by being redirected to the following music video
COOL_MV = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

urlpatterns = [
    path(r"admin/", admin.site.urls),
    path(r"aincrad/", include("aincrad.urls")),
    path(r"arch/", include("arch.urls")),
    path(r"core/", include("core.urls")),
    path(r"dash/", include("dashboard.urls")),
    path(r"exams/", include("exams.urls")),
    path(r"hanabi/", include("hanabi.urls")),
    path(r"markets/", include("markets.urls")),
    path(r"mouse/", include("mouse.urls")),
    path(r"opal/", include("opal.urls")),
    path(r"roster/", include("roster.urls")),
    path(r"rpg/", include("rpg.urls")),
    path(r"payments/", include("payments.urls")),
    path(r"suggestions/", include("suggestions.urls")),
    path(r"tubes/", include("tubes.urls")),
    # ------
    path(r"hijack/", include("hijack.urls")),
    path(r"accounts/", include("allauth.urls")),
    path(r"notifications/", include("django_nyt.urls")),
    path(r"wiki/", include("wiki.urls")),
    path(r"fandom/", include("wikihaxx.urls")),
    path(r"__debug__/", include(debug_toolbar.urls)),
    path(
        r"robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
    path(
        r"favicon.ico",
        RedirectView.as_view(url="https://web.evanchen.cc/favicon.ico"),
    ),
    path(
        r"apple-touch-icon.png",
        RedirectView.as_view(url="https://web.evanchen.cc/icons/apple-touch-icon.png"),
    ),
    path(
        r"apple-touch-icon-precomposed.png",
        RedirectView.as_view(url="https://web.evanchen.cc/icons/apple-touch-icon.png"),
    ),
    path(
        r"apple-touch-icon-152x152.png",
        RedirectView.as_view(
            url="https://web.evanchen.cc/icons/apple-touch-icon-152x152.png"
        ),
    ),
    path(
        r"apple-touch-icon-152x152-precomposed.png",
        RedirectView.as_view(
            url="https://web.evanchen.cc/icons/apple-touch-icon-152x152.png"
        ),
    ),
    path(r"wp-admin/", RedirectView.as_view(url=COOL_MV)),
    path(r"wp-admin/<path:path>", RedirectView.as_view(url=COOL_MV)),
    path(r"wp-content/<path:path>", RedirectView.as_view(url=COOL_MV)),
    path(r"wp-includes/<path:path>", RedirectView.as_view(url=COOL_MV)),
    path(r"file-manager/<path:path>", RedirectView.as_view(url=COOL_MV)),
    path(r"public/<path:path>", RedirectView.as_view(url=COOL_MV)),
    path(r"vendor/<path:path>", RedirectView.as_view(url=COOL_MV)),
    path(r"laravel-file-manager/<path:path>", RedirectView.as_view(url=COOL_MV)),
    path(r".well-known/<path:path>", RedirectView.as_view(url=COOL_MV)),
    re_path(r".*\.php$", RedirectView.as_view(url=COOL_MV)),
    re_path(r".*wlwmanifest\.xml$", RedirectView.as_view(url=COOL_MV)),
    path(r"", RedirectView.as_view(pattern_name="index"), name="top"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # type: ignore

if settings.DEBUG:
    admin.site.site_header = "127.0.0.1"
    admin.site.index_title = "Switchboard"
    admin.site.site_title = "otis@localhost"
else:  # pragma: no cover
    admin.site.site_header = "OTIS Headquarters"
    admin.site.index_title = "GM Panel"
    admin.site.site_title = "OTIS HQ"
