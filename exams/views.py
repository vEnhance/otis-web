from django.shortcuts import render, get_object_or_404
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from typing import Any, Dict
from exams.forms import ExamAttemptForm
import exams.models
import roster.models

# Create your views here.

def attempt_exam(request : HttpRequest, pk : int, student_id : int) -> HttpResponse:
	context : Dict[str, Any] = {}
	quiz = get_object_or_404(exams.models.Quiz, pk = pk)
	# TODO : we're gonna replace the middleware in a bit, so this is a stopgap
	student = get_object_or_404(roster.models.Student, id = student_id)
	if request.method == 'POST':
		form = ExamAttemptForm(request.POST)
		if form.is_valid():
			attempt = form.save(commit=False)
			attempt.quiz = quiz
			attempt.student = student
			return HttpResponseRedirect(reverse_lazy())
	return render(request, 'exams/quiz_form.html', context)

def show_exam(request : HttpRequest, pk : int, student_id : int) -> HttpResponse:
	raise NotImplementedError()
