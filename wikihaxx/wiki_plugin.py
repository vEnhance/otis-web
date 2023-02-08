from __future__ import absolute_import, unicode_literals

from typing import Any

from django.utils.translation import gettext_lazy as _
from wiki.core.plugins import registry
from wiki.core.plugins.base import BasePlugin

from . import settings
from .mdx.otis import OTISExtension


class HaxxPlugin(BasePlugin):
    slug = settings.SLUG

    sidebar: dict[str, Any] = {
        "headline": _("OTIS"),
        "icon_class": "fa-info-circle",
        "template": "wikihaxx/sidebar.html",
        "form_class": None,
        "get_form_kwargs": (lambda a: {}),  # pragma: no cover
    }

    markdown_extensions = [
        OTISExtension(),
    ]


registry.register(HaxxPlugin)
