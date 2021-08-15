from typing import Any, Dict, Optional

from core.utils import get_from_google_storage
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from roster.utils import get_student_by_id, infer_student

from exams.calculator import expr_compute

from .forms import ExamAttemptForm
from .models import ExamAttempt, PracticeExam

# Create your views here.


def pdf(request: HttpRequest, pk: int) -> HttpResponse:
	exam = get_object_or_404(PracticeExam, pk=pk)
	if getattr(request.user, 'is_staff', True):
		return get_from_google_storage(exam.pdfname)

	student = infer_student(request)
	if not exam.started:
		return HttpResponseForbidden("Not ready to download this exam yet")
	elif student.semester.exam_family != exam.family:
		return HttpResponseForbidden("You can't access this quiz.")

	return get_from_google_storage(exam.pdfname)


def quiz(request: HttpRequest, student_id: int, pk: int) -> HttpResponse:
	student = get_student_by_id(request, student_id)
	context: Dict[str, Any] = {}
	quiz = get_object_or_404(PracticeExam, pk=pk)
	if quiz.is_test:
		return HttpResponseForbidden("You can't submit numerical answers to an olympiad exam.")
	if not quiz.started:
		return HttpResponseForbidden("You can't start this quiz")

	if student.semester.exam_family != quiz.family:
		return HttpResponseForbidden("You can't access this quiz.")

	attempt: Optional[ExamAttempt] = None
	try:
		attempt = ExamAttempt.objects.get(student=student, quiz=pk)
	except ExamAttempt.DoesNotExist:
		if request.method == 'POST':
			if quiz.overdue:
				return HttpResponseForbidden("You can't submit this quiz since the deadline passed.")
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
		dummy_form = ExamAttemptForm(instance=attempt)
		for i in range(1, 6):
			dummy_form.fields[f'guess{i}'].disabled = True
		context['rows'] = []

		score = 0
		for i in range(1, 6):
			field = dummy_form.visible_fields()[i - 1]
			guess_str = getattr(attempt, f'guess{i}')
			guess_val = expr_compute(guess_str)
			accepted_str = getattr(quiz, f'answer{i}')
			accepted_vals = [expr_compute(_) for _ in accepted_str.split(',') if _]
			if guess_val is not None:
				correct = any(v is not None and abs(guess_val - v) < 1e-12 for v in accepted_vals)
			else:
				correct = False

			context['rows'].append(
				{
					'field': field,
					'accepted': accepted_str,
					'correct': correct,
					'url': getattr(quiz, f'url{i}', None)
				}
			)
			if correct:
				score += 1

			if attempt.score != score:
				attempt.score = score
				attempt.save()

	context['quiz'] = quiz
	context['student'] = student
	return render(request, 'exams/quiz.html', context)


def show_exam(request: HttpRequest, student_id: int, pk: int) -> HttpResponse:
	context: Dict[str, Any] = {}
	quiz = get_object_or_404(PracticeExam, pk=pk)
	if quiz.is_test:
		return HttpResponseForbidden("You can only use this view for short-answer quizzes.")
	return render(request, 'exams/quiz_detail.html', context)
