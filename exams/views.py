from typing import Any, Dict, Optional

import roster.models
import roster.utils
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

import exams.models
from exams.forms import ExamAttemptForm

# Create your views here.

def quiz(request : HttpRequest, student_id : int, pk : int) -> HttpResponse:
	context : Dict[str, Any] = {}
	quiz = get_object_or_404(exams.models.PracticeExam, pk = pk)
	if quiz.is_test:
		return HttpResponseForbidden("You can't submit numerical answers to an olympiad exam.")
	student = get_object_or_404(roster.models.Student, id = student_id)
	roster.utils.check_can_view(request, student)
	if not quiz.started:
		return HttpResponseForbidden("You can't start this quiz")

	attempt : Optional[exams.models.ExamAttempt] = None
	try:
		attempt = exams.models.ExamAttempt.objects.get(student=student, quiz=pk)
	except exams.models.ExamAttempt.DoesNotExist:
		if request.method == 'POST':
			if quiz.overdue:
				return HttpResponseForbidden("You can't submit this quiz " \
						"since the deadline passed.")
			form = ExamAttemptForm(request.POST)
			if form.is_valid():
				attempt = form.save(commit=False)
				assert attempt is not None
				attempt.quiz = quiz
				attempt.student = student
				attempt.save()
				context['finished'] = True
			else:
				context['finished'] = False
	else:
		context['finished'] = True
		if request.method == 'POST':
			return HttpResponseForbidden('You already submitted this quiz')

	if attempt is not None:
		form = ExamAttemptForm(instance = attempt)
		for i in range(1,6):
			form.fields[f'guess{i}'].disabled = True
	elif request.method != 'POST':
		form = ExamAttemptForm()

	context['form'] = form
	context['quiz'] = quiz
	context['student'] = student
	return render(request, 'exams/quiz.html', context)

def show_exam(request : HttpRequest,  student_id : int, pk : int) -> HttpResponse:
	context : Dict[str, Any] = {}
	quiz = get_object_or_404(exams.models.PracticeExam, pk = pk)
	if quiz.is_test:
		return HttpResponseForbidden("You can only use this view for short-answer quizzes.")
	student = get_object_or_404(roster.models.Student, id = student_id)
	roster.utils.check_can_view(request, student)
	return render(request, 'exams/quiz_detail.html', context)
