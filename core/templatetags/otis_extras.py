from django import template
from django.urls import reverse

register = template.Library()

@register.simple_tag
def view_problems(unit):
	return reverse("view-problems", args=(unit.id,))

@register.simple_tag
def view_solutions(unit):
	return reverse("view-solutions", args=(unit.id,))

@register.simple_tag
def view_tex(unit):
	return reverse("view-tex", args=(unit.id,))

@register.filter(name='display_initial_choice')
def display_initial_choice(field):
	return ' '.join([ucode for (uid, ucode) in field.field._choices\
			if uid in field.initial])
