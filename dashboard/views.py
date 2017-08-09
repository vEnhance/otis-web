# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

import core
import roster

@login_required
def dashboard(request, student_id):
	student = get_object_or_404(roster.models.Student.objects, id = student_id)
	if student.user != request.user and student.assistant != request.user and not request.user.is_staff:
		return HttpResponse("Permission denied")
	
	context = {}
	context['title'] = "Dashboard for " + student.name
	context['student'] = student
	context['curriculum'] = enumerate(student.curriculum.all())
	context['omniscient'] = False # request.user.is_staff or student.assistant == request.user
	return render(request, "dashboard/dashboard.html", context)



# Create your views here.
