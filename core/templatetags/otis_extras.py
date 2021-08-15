from core.models import Unit
from django import template
from django.forms.boundfield import BoundField
from django.urls import reverse
from roster.models import Student

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


@register.filter(name='level')
def level(student: Student) -> int:
	spades = (getattr(student, 'spades_quizzes', 0) or 0) + (student.usemo_score or 0)
	spade_level = int(spades**0.5)
	return sum(
		int((getattr(student, key, 0) or 0)**0.5) for key in ('clubs', 'hearts', 'diamonds')
	) + spade_level
