from django.shortcuts import render
from django.http import HttpResponse

import itertools

import core
import roster

# Create your views here.

def curriculum(request, student_id):
	student = roster.models.Student.objects.get(id = student_id)
	units = core.models.Unit.objects.all()

	for name, group in itertools.groupby(units, lambda u : u.name):
		print name
		for _ in group:
			print _.code
	return HttpResponse(student.name)
