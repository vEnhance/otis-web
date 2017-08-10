# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

import core
import exams
import roster

@login_required
def dashboard(request, student_id):
	student = get_object_or_404(roster.models.Student.objects, id = student_id)
	if student.user != request.user and student.assistant != request.user and not request.user.is_staff:
		return HttpResponse("Permission denied")
	
	context = {}
	context['title'] = "Dashboard for " + student.name
	context['student'] = student
	context['curriculum'] = student.curriculum.all()
	context['omniscient'] = False # request.user.is_staff or student.assistant == request.user
	context['olympiads'] = exams.models.MockOlympiad.objects.filter(due_date__isnull=False)
	context['assignments'] = exams.models.Assignment.objects.filter(semester__active=True)
	return render(request, "dashboard/dashboard.html", context)



# Create your views here.
