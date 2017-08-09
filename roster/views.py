from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse

import itertools

import core
import roster

# Create your views here.

def curriculum(request, student_id):
	student = get_object_or_404(roster.models.Student.objects, id = student_id)
	units = core.models.Unit.objects.all()

	for name, group in itertools.groupby(units, lambda u : u.name):
		print name
		for _ in group:
			print _.code
	context = {'title' : 'purr', 'content' : student.name}
	# return HttpResponse("hi")
	return render(request, "layout.html", context)
