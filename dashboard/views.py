# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

import core
import dashboard
import exams
import roster

@login_required
def main(request, student_id):
	student = get_object_or_404(roster.models.Student.objects, id = student_id)
	if not student.can_view_by(request.user):
		return HttpResponse("Permission denied")
	
	context = {}
	context['title'] = "Dashboard for " + student.name
	context['student'] = student
	context['curriculum'] = student.curriculum.all()
	context['omniscient'] = student.is_taught_by(request.user)
	context['olympiads'] = exams.models.MockOlympiad.objects.filter(due_date__isnull=False)
	context['assignments'] = exams.models.Assignment.objects.filter(semester__active=True)
	return render(request, "dashboard/main.html", context)

@login_required
def uploads(request, student_id, unit_id):
	student = get_object_or_404(roster.models.Student.objects, id = student_id)
	if unit_id == "0":
		unit = None
	else:
		unit = get_object_or_404(core.models.Unit.objects, id = unit_id)\
				if unit_id else None
	if not student.can_view_by(request.user):
		return HttpResponse("Permission denied")

	context = {}
	context['title'] = 'File Uploads'
	context['student'] = student
	context['files'] = dashboard.models.UploadedFile.objects\
			.filter(benefactor=student, unit=unit)
	# TODO form for adding new files
	return render(request, "dashboard/uploads.html", context)
