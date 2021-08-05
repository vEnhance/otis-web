from typing import Any, Dict

import roster.models
import roster.utils
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.http.response import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy

import exams.models
from exams.forms import ExamAttemptForm

# Create your views here.

def attempt_exam(request : HttpRequest, student_id : int, pk : int) -> HttpResponse:
	context : Dict[str, Any] = {}
	quiz = get_object_or_404(exams.models.Quiz, pk = pk)
	student = get_object_or_404(roster.models.Student, id = student_id)
	roster.utils.check_can_view(request, student)

	if quiz.exam.overdue or not quiz.exam.started:
		return HttpResponseForbidden("You can't start this quiz")
	# TODO redirect if already finished
	
	if request.method == 'POST':
		form = ExamAttemptForm(request.POST)
		if form.is_valid():
			attempt = form.save(commit=False)
			attempt.quiz = quiz
			attempt.student = student
			attempt.save()
			return HttpResponseRedirect(
					reverse_lazy('show-exam', args=(student.id, pk)))
		form = ExamAttemptForm()
	else:
		form = ExamAttemptForm()

	context['form'] = form
	context['quiz'] = quiz
	context['student'] = student
	return render(request, 'exams/quiz_form.html', context)

def show_exam(request : HttpRequest,  student_id : int, pk : int) -> HttpResponse:
	context : Dict[str, Any] = {}
	quiz = get_object_or_404(exams.models.Quiz, pk = pk)
	student = get_object_or_404(roster.models.Student, id = student_id)
	roster.utils.check_can_view(request, student)
	return render(request, 'exams/quiz_detail.html', context)
