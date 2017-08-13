from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse


import itertools

import core
import roster
import forms

# Create your views here.

@staff_member_required
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
			messages.success(request, "Successfully saved curriculum.")
	else:
		form = forms.CurriculumForm(units = units, original = original)

	context = {'title' : "Curriculum for " + student.name,
			'student' : student, 'form' : form}
	# return HttpResponse("hi")
	return render(request, "roster/curredit.html", context)

@login_required
def advance(request, student_id):
	student = get_object_or_404(roster.models.Student.objects, id = student_id)
	if request.method == 'POST':
		form = forms.AdvanceForm(request.POST, instance = student)
		if form.is_valid():
			form.save()
			messages.success(request, "Successfully advanced student.")
			return HttpResponseRedirect(reverse("dashboard", args=(student_id,)))
	else:
		form = forms.AdvanceForm(instance = student)

	context = {'title' : "Advance " + student.name}
	context['form'] = form
	context['student'] = student
	context['curriculum'] = student.curriculum.all()
	context['omniscient'] = student.is_taught_by(request.user) # TODO ugly, template tag `omniscient`
	return render(request, "roster/advance.html", context)

