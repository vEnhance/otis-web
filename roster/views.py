from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse

import itertools

import core
import roster
import forms

# Create your views here.

def curriculum(request, student_id):
	student = get_object_or_404(roster.models.Student.objects, id = student_id)
	units = core.models.Unit.objects.all()

	form = forms.CurriculumForm(units = units,
			original = student.curriculum.values_list('id', flat=True))

	context = {'title' : student.name, 'content' : form}
	# return HttpResponse("hi")
	return render(request, "layout.html", context)
