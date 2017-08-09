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
	original = student.curriculum.values_list('id', flat=True)

	if request.method == 'POST':
		form = forms.CurriculumForm(request.POST, units = units)
		if form.is_valid():
			data = form.cleaned_data
			values = [data[k] for k in data if k.startswith('group-') and data[k] is not None]
			student.curriculum = values
			student.save()
	else:
		form = forms.CurriculumForm(units = units, original = original)

	context = {'title' : "Curriculum for " + student.name,
			'student' : student, 'form' : form}
	# return HttpResponse("hi")
	return render(request, "roster/curredit.html", context)
