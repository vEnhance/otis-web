import datetime
import os
import re
from typing import Literal

from django import template
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.forms.boundfield import BoundField
from django.template.defaultfilters import stringfilter
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.functional import keep_lazy_text
from django.utils.html import escape
from django.utils.safestring import SafeData, mark_safe
from django.utils.text import normalize_newlines
from django.utils.timezone import template_localtime  # type: ignore

from core.models import Unit, UserProfile
from core.utils import find_profile
from rpg.levelsys import BONUS_D_UNIT, BONUS_Z_UNIT

register = template.Library()


@register.simple_tag
def view_problems(unit: Unit) -> str:
    return reverse("view-problems", args=(unit.pk,))


@register.simple_tag
def view_solutions(unit: Unit) -> str:
    return reverse("view-solutions", args=(unit.pk,))


@register.simple_tag
def view_tex(unit: Unit) -> str:
    return reverse("view-tex", args=(unit.pk,))


@register.filter(name="display_initial_choice")
def display_initial_choice(field: BoundField) -> str:
    choices = field.field._choices  # type: ignore
    return " ".join([ucode for (uid, ucode) in choices if uid in field.initial])


@register.filter(name="getenv")
def getenv(s: str) -> str:
    return os.getenv(s) or ""


@register.filter(name="getprofile")
def getprofile(user: User | AnonymousUser) -> UserProfile | None:
    if isinstance(user, AnonymousUser):
        return None
    return find_profile(user)


@register.filter(name="getconfig")
def getconfig(user: User | AnonymousUser, config: str) -> bool:
    profile = getprofile(user)
    return getattr(profile, config) if profile is not None else False


@register.filter(name="clubs_multiplier")
def clubs_multiplier(u: Unit) -> str:
    if u.code[0] == "D":
        return f"(×{1 + BONUS_D_UNIT})"
    elif u.code[0] == "Z":
        return f"(×{1 + BONUS_Z_UNIT})"
    else:
        return ""


@keep_lazy_text
def parbreaks(value: str, autoescape=False):
    """Convert doubled paragraph breaks into <p>."""
    value = normalize_newlines(value)
    paras = re.split("\n{2,}", str(value))
    if autoescape:
        paras = [f"<p>{escape(p)}</p>" for p in paras]
    else:
        paras = [f"<p>{p}</p>" for p in paras]
    return "\n\n".join(paras)


@register.filter("parbreaks", is_safe=True, needs_autoescape=True)
@stringfilter
def parbreaks_filter(value: str, autoescape=True) -> str:
    """
    Replace paragraph breaks in plain text with appropriate HTML; a new line
    followed by a blank line becomes a paragraph break (``</p>``).
    """
    autoescape = autoescape and not isinstance(value, SafeData)
    return mark_safe(parbreaks(value, autoescape))


TimestampStyle = Literal["relative", "date", "isodate", "time", "isotime"]

# resolved with use_l10n=False so `date_format` uses settings, not locale.
TIMESTAMP_FORMATS: dict[TimestampStyle, str] = {
    "date": "DATE_FORMAT",
    "isodate": "SHORT_DATE_FORMAT",
    "time": "DATETIME_FORMAT",
    "isotime": "SHORT_DATETIME_FORMAT",
}

# when only a date is given, convert literal to a suitable type
DATE_ONLY_STYLES: dict[TimestampStyle, TimestampStyle] = {
    "relative": "date",
    "time": "date",
    "isotime": "isodate",
}


@register.inclusion_tag("core/components/timestamp.html")
def timestamp(
    value: datetime.date | None,
    style: TimestampStyle,
    default: str = "",
) -> dict[str, str]:
    """
    Render a ``<time>`` element for a date or datetime.

    Use the ISO styles for admin pages and data-heavy tables, and the
    spelled-out styles everywhere else.
    """
    if value is None:
        return {"default": default}
    local: datetime.date = template_localtime(value)
    is_datetime = isinstance(local, datetime.datetime)
    if not is_datetime:
        style = DATE_ONLY_STYLES.get(style, style)
    if style == "relative" and isinstance(local, datetime.datetime):
        text = naturaltime(local)
    elif style in TIMESTAMP_FORMATS:
        text = date_format(local, TIMESTAMP_FORMATS[style], use_l10n=False)
    else:
        raise ValueError(f"Unknown timestamp style {style!r}")
    return {
        "iso": date_format(local, "c", use_l10n=False),
        "full": date_format(local, "r", use_l10n=False) if is_datetime else "",
        "text": text,
    }
