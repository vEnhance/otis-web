from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from otisweb.utils import AuthHttpRequest
from roster.models import Student

from .forms import SIGNED, SurveyForm
from .models import GMFeedback, InstructorComment, Survey, SurveyCompletion


@login_required
def survey_list(request: AuthHttpRequest) -> HttpResponse:
    if request.user.is_superuser:
        surveys = Survey.objects.all()
    else:
        # Students don't see a survey before it opens.
        surveys = Survey.objects.filter(
            semester__student__user=request.user,
            opens_at__lte=timezone.now(),
        )
    surveys = surveys.select_related("semester").order_by("-opens_at")
    completed = set(
        SurveyCompletion.objects.filter(student__user=request.user).values_list(
            "survey_id", flat=True
        )
    )
    rows = [{"survey": s, "completed": s.pk in completed} for s in surveys]
    return render(request, "surveys/survey_list.html", {"rows": rows})


def _get_student(request: AuthHttpRequest, survey: Survey) -> Student | None:
    return Student.objects.filter(user=request.user, semester=survey.semester).first()


def _render_detail(
    request: AuthHttpRequest,
    survey: Survey,
    student: Student | None,
    form: SurveyForm | None = None,
) -> HttpResponse:
    context: dict[str, Any] = {"survey": survey, "student": student}
    if student is None:
        # Only superusers get here: a preview of the empty form.
        context["form"] = SurveyForm(survey=survey, student=None)
        context["preview"] = True
    elif SurveyCompletion.objects.filter(survey=survey, student=student).exists():
        context["completed"] = True
        context["gm_feedback"] = GMFeedback.objects.filter(
            survey=survey, student=student
        ).first()
        context["instructor_comment"] = (
            InstructorComment.objects.filter(survey=survey, student=student)
            .select_related("assistant")
            .first()
        )
    elif survey.is_open:
        context["form"] = form or SurveyForm(survey=survey, student=student)
    return render(request, "surveys/survey_detail.html", context)


@login_required
def survey_detail(request: AuthHttpRequest, survey_pk: int) -> HttpResponse:
    survey = get_object_or_404(Survey.objects.select_related("semester"), pk=survey_pk)
    student = _get_student(request, survey)
    if student is None and not request.user.is_superuser:
        raise PermissionDenied("You aren't a student in this semester.")
    return _render_detail(request, survey, student)


@login_required
def survey_submit(request: AuthHttpRequest, survey_pk: int) -> HttpResponse:
    survey = get_object_or_404(Survey.objects.select_related("semester"), pk=survey_pk)
    if request.method != "POST":
        return redirect("survey-detail", survey.pk)
    student = _get_student(request, survey)
    if student is None:
        raise PermissionDenied("You aren't a student in this semester.")
    if not survey.is_open:
        messages.error(request, "This survey isn't accepting responses.")
        return redirect("survey-detail", survey.pk)

    form = SurveyForm(request.POST, survey=survey, student=student)
    if not form.is_valid():
        return _render_detail(request, survey, student, form)
    data = form.cleaned_data

    with transaction.atomic():
        try:
            # A savepoint, so a duplicate submission (even a concurrent one) fails
            # on the unique constraint without breaking the outer transaction.
            with transaction.atomic():
                SurveyCompletion.objects.create(survey=survey, student=student)
        except IntegrityError:
            messages.error(request, "You already submitted this survey.")
            return redirect("survey-detail", survey.pk)
        GMFeedback.objects.create(
            survey=survey,
            student=student if data["gm_signed"] == SIGNED else None,
            essay=data["essay"],
            satisfaction=data.get("satisfaction"),
            anything_else=data.get("anything_else", ""),
        )
        if data.get("instructor_comments"):
            assert student.assistant is not None  # the form drops the field otherwise
            InstructorComment.objects.create(
                survey=survey,
                student=student if data["instructor_signed"] == SIGNED else None,
                assistant=student.assistant,
                comments=data["instructor_comments"],
            )

    messages.success(
        request,
        "Thanks for submitting. "
        "If you don't have the diamond for this survey, "
        "it'll be awarded when the survey closes.",
    )
    return redirect("survey-detail", survey.pk)
