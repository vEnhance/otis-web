from typing import Any, Optional

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.http.response import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from core.utils import get_from_google_storage
from exams.calculator import expr_compute
from otisweb.utils import AuthHttpRequest
from roster.utils import get_student_by_pk, infer_student

from .forms import ExamAttemptForm
from .models import ExamAttempt, PracticeExam

# Create your views here.


@login_required
def pdf(request: AuthHttpRequest, pk: int) -> HttpResponse:
    exam = get_object_or_404(PracticeExam, pk=pk)
    if request.user.is_staff:
        return get_from_google_storage(exam.pdfname)

    student = infer_student(request)
    if not exam.started:
        return HttpResponseForbidden("Not ready to download this exam yet")
    elif student.semester.exam_family != exam.family:
        return HttpResponseForbidden("You can't access this quiz.")
    elif not student.enabled:
        return HttpResponseForbidden("Your student account is disabled.")

    return get_from_google_storage(exam.pdfname)


@login_required
def quiz(request: AuthHttpRequest, student_pk: int, pk: int) -> HttpResponse:
    student = get_student_by_pk(request, student_pk)
    context: dict[str, Any] = {}
    quiz = get_object_or_404(PracticeExam, pk=pk)
    if quiz.is_test:
        return HttpResponseForbidden(
            "You can't submit numerical answers to an olympiad exam."
        )
    if not quiz.started:
        return HttpResponseForbidden("You can't start this quiz")
    if not student.enabled:
        return HttpResponseForbidden("Your student account is disabled.")

    if student.semester.exam_family != quiz.family:
        return HttpResponseForbidden("You can't access this quiz.")

    attempt: Optional[ExamAttempt] = None
    try:
        attempt = ExamAttempt.objects.get(student=student, quiz=pk)
    except ExamAttempt.DoesNotExist:
        if request.method == "POST":
            if quiz.overdue:
                return HttpResponseForbidden(
                    "You can't submit this quiz since the deadline passed."
                )
            if student.semester.active is False:
                return HttpResponseForbidden(
                    "You can't submit quizzes for archived semesters."
                )
            form = ExamAttemptForm(request.POST)
            if form.is_valid():
                attempt = form.save(commit=False)
                assert attempt is not None
                attempt.quiz = quiz
                attempt.student = student
        else:
            form = ExamAttemptForm()
        context["form"] = form
    else:
        if request.method == "POST":
            return HttpResponseForbidden("You already submitted this quiz")

    if attempt is not None:
        context["attempt"] = attempt
        dummy_form = ExamAttemptForm(instance=attempt)
        for i in range(1, 6):
            dummy_form.fields[f"guess{i}"].disabled = True
        context["rows"] = []

        score = 0
        for i in range(1, 6):
            field = dummy_form.visible_fields()[i - 1]
            guess_str = getattr(attempt, f"guess{i}")
            guess_val = expr_compute(guess_str)
            accepted_str = getattr(quiz, f"answer{i}")
            accepted_vals = [expr_compute(_) for _ in accepted_str.split(",") if _]
            if len(guess_str.replace(" ", "")) > 24:
                correct = False
            elif len([_ for _ in guess_str if _ in "+-*/^"]) > 4:
                correct = False
            elif guess_val is not None:
                correct = any(
                    v is not None and abs(guess_val - v) < 1e-12 for v in accepted_vals
                )
            else:
                correct = False

            context["rows"].append(
                {
                    "field": field,
                    "accepted": accepted_str,
                    "correct": correct,
                    "url": getattr(quiz, f"url{i}", None),
                }
            )
            if correct:
                score += 1

        if attempt.score is None:
            attempt.score = score
            attempt.save()

    context["quiz"] = quiz
    context["student"] = student
    return render(request, "exams/quiz.html", context)
