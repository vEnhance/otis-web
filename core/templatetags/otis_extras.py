import os
import re
from typing import Optional

from django import template
from django.contrib.auth.models import AnonymousUser, User
from django.forms.boundfield import BoundField
from django.template.defaultfilters import stringfilter
from django.urls import reverse
from django.utils.functional import keep_lazy_text
from django.utils.html import escape
from django.utils.safestring import SafeData, mark_safe
from django.utils.text import normalize_newlines

from core.models import Unit, UserProfile
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
def getprofile(user: User) -> Optional[UserProfile]:
    try:
        return UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return None


@register.filter(name="getconfig")
def getconfig(user: User, config: str) -> bool:
    if isinstance(user, AnonymousUser):
        return False
    try:
        profile: UserProfile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return False
    else:
        return getattr(profile, config)


@register.filter(name="clubs_multiplier")
def clubs_multiplier(u: Unit) -> str:
    if u.code[0] == "D":
        return f"(×{1+BONUS_D_UNIT})"
    elif u.code[0] == "Z":
        return f"(×{1+BONUS_Z_UNIT})"
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
