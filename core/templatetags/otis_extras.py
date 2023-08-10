import os
from typing import Any, Optional

from django import template
from django.contrib.auth.models import User
from django.forms.boundfield import BoundField
from django.urls import reverse

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


@register.filter(name="clubs_multiplier")
def clubs_multiplier(u: Unit) -> str:
    if u.code[0] == "D":
        return f"(×{1+BONUS_D_UNIT})"
    elif u.code[0] == "Z":
        return f"(×{1+BONUS_Z_UNIT})"
    else:
        return ""
