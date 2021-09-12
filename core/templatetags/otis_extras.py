import os

from core.models import Unit
from dashboard.levelsys import BONUS_D_UNIT, BONUS_Z_UNIT
from django import template
from django.forms.boundfield import BoundField
from django.urls import reverse

register = template.Library()


@register.simple_tag
def view_problems(unit: Unit):
	return reverse("view-problems", args=(unit.pk, ))


@register.simple_tag
def view_solutions(unit: Unit):
	return reverse("view-solutions", args=(unit.pk, ))


@register.simple_tag
def view_tex(unit: Unit):
	return reverse("view-tex", args=(unit.pk, ))


@register.filter(name='display_initial_choice')
def display_initial_choice(field: BoundField):
	choices = field.field._choices  # type: ignore
	return ' '.join([ucode for (uid, ucode) in choices if uid in field.initial])


@register.filter(name='getenv')
def getenv(s: str) -> str:
	return os.getenv(s) or ''


@register.filter(name='clubs_multiplier')
def clubs_multiplier(u: Unit) -> str:
	if u.code[0] == 'D':
		return f'(×{1+BONUS_D_UNIT})'
	elif u.code[0] == 'Z':
		return f'(×{1+BONUS_Z_UNIT})'
	else:
		return ''
