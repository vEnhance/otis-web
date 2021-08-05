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

	if student.semester.exam_family != quiz.family:
		return HttpResponseForbidden("You can't access this quiz.")

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
		else:
			form = ExamAttemptForm()
		context['form'] = form
	else:
		if request.method == 'POST':
			return HttpResponseForbidden('You already submitted this quiz')

	if attempt is not None:
		context['attempt'] = attempt
		dummy_form = ExamAttemptForm(instance = attempt)
		for i in range(1,6):
			dummy_form.fields[f'guess{i}'].disabled = True
		context['rows'] = []

		score = 0
		for i in range(1,6):
			field = dummy_form.visible_fields()[i-1]
			guess = getattr(attempt, f'guess{i}')
			accepted = getattr(quiz, f'answer{i}')
			correct = guess in [int(_) for _ in accepted.split(',') if _]
			context['rows'].append(
					{ 'field' : field,
						'accepted' : accepted.replace(',', ' '),
						'correct' : correct,
						'url' : getattr(quiz, f'url{i}', None)
						})
			if correct:
				score += 1

			if attempt.score != score:
				attempt.score = score
				attempt.save()

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
