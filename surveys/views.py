import uuid
from typing import Any

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.paginator import Page, Paginator
from django.db import IntegrityError, models, transaction
from django.db.models import Count, Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from otisweb.decorators import admin_required, staff_required, verified_required
from otisweb.mixins import AdminRequiredMixin, StaffRequiredMixin
from otisweb.utils import AuthHttpRequest
from roster.models import Student

from .forms import ANONYMOUS_LINK, SIGNED, SurveyForm
from .models import GMFeedback, InstructorComment, Survey, SurveyCompletion

RESPONSES_PER_PAGE = 20

# The inbox status dropdown: query value -> (label, filter).
type StatusFilters = dict[str, tuple[str, Q]]

# Unread by default: an inbox is opened to work through what's new in it.
DEFAULT_STATUS = "unread"
READ_FILTERS: StatusFilters = {
    "all": ("All", Q()),
    DEFAULT_STATUS: ("📬 Unread", Q(is_read=False)),
    "read": ("📭 Read", Q(is_read=True)),
}
# These overlap, since replying marks feedback read, but one dropdown is simpler
# than two for what's a handful of responses per survey.
REPLY_FILTERS: StatusFilters = {
    **READ_FILTERS,
    "replied": ("💬 Replied", ~Q(reply="")),
    "unreplied": ("🤐 Not replied", Q(reply="")),
}


@verified_required
def survey_list(request: AuthHttpRequest) -> HttpResponse:
    user = request.user
    now = timezone.now()
    student_semesters = Student.objects.filter(user=user).values("semester")
    taught_semesters = Student.objects.filter(assistant__user=user).values("semester")
    if user.is_superuser:
        surveys = Survey.objects.all()
    else:
        # Students don't see a survey before it opens; instructors do, to preview it.
        surveys = Survey.objects.filter(
            Q(semester__in=student_semesters, opens_at__lte=now)
            | Q(semester__in=taught_semesters)
        )
    surveys = (
        surveys.select_related("semester")
        .annotate(
            num_completions=Count("surveycompletion", distinct=True),
            num_unread_feedback=Count(
                "gmfeedback", filter=Q(gmfeedback__is_read=False), distinct=True
            ),
            num_comments=Count(
                "instructorcomment",
                filter=Q(instructorcomment__assistant__user=user),
                distinct=True,
            ),
            num_unread_comments=Count(
                "instructorcomment",
                filter=Q(
                    instructorcomment__assistant__user=user,
                    instructorcomment__is_read=False,
                ),
                distinct=True,
            ),
        )
        .order_by("-opens_at")
    )
    completed = set(
        SurveyCompletion.objects.filter(student__user=user).values_list(
            "survey_id", flat=True
        )
    )
    signed_feedback = {
        feedback.survey.pk: feedback
        for feedback in GMFeedback.objects.filter(student__user=user).select_related(
            "survey"
        )
    }
    student_semester_ids = set(student_semesters.values_list("semester", flat=True))
    taught_semester_ids = set(taught_semesters.values_list("semester", flat=True))
    rows = [
        {
            "survey": s,
            "status": "upcoming"
            if now < s.opens_at
            else "open"
            if now < s.closes_at
            else "closed",
            "is_student": s.semester.pk in student_semester_ids,
            "is_instructor": s.semester.pk in taught_semester_ids,
            "completed": s.pk in completed,
            "gm_feedback": signed_feedback.get(s.pk),
        }
        for s in surveys
    ]
    return render(request, "surveys/survey_list.html", {"rows": rows})


def _get_student(request: AuthHttpRequest, survey: Survey) -> Student | None:
    return Student.objects.filter(user=request.user, semester=survey.semester).first()


def _can_preview(user: User, survey: Survey) -> bool:
    """Superusers, and instructors of a student in the survey's semester."""
    return (
        user.is_superuser
        or Student.objects.filter(
            semester=survey.semester, assistant__user=user
        ).exists()
    )


def _render_detail(
    request: AuthHttpRequest,
    survey: Survey,
    student: Student | None,
    form: SurveyForm | None = None,
) -> HttpResponse:
    context: dict[str, Any] = {"survey": survey, "student": student}
    if student is None:
        # Only superusers and instructors get here: a preview of the empty form.
        context["form"] = SurveyForm(survey=survey, student=None)
        context["preview"] = True
    elif SurveyCompletion.objects.filter(survey=survey, student=student).exists():
        context["completed"] = True
        context["gm_feedback"] = GMFeedback.objects.filter(
            survey=survey, student=student
        ).first()
        if context["gm_feedback"] is None:
            # Anonymous, so we can't link it, but can say what to search history for.
            placeholder = uuid.UUID(int=0)
            context["private_link_prefix"] = request.build_absolute_uri(
                reverse("survey-gm-feedback", args=[survey.pk, placeholder])
            ).removesuffix(f"{placeholder}/")
        context["instructor_comment"] = (
            InstructorComment.objects.filter(survey=survey, student=student)
            .select_related("assistant")
            .first()
        )
    elif survey.is_open:
        context["form"] = form or SurveyForm(survey=survey, student=student)
    return render(request, "surveys/survey_detail.html", context)


@verified_required
def survey_detail(request: AuthHttpRequest, survey_pk: int) -> HttpResponse:
    survey = get_object_or_404(Survey.objects.select_related("semester"), pk=survey_pk)
    student = _get_student(request, survey)
    if student is None and not _can_preview(request.user, survey):
        raise PermissionDenied("You aren't a student in this semester.")
    return _render_detail(request, survey, student)


@verified_required
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
        gm_feedback = GMFeedback.objects.create(
            survey=survey,
            student=student if data["gm_identity"] == SIGNED else None,
            token=uuid.uuid4() if data["gm_identity"] == ANONYMOUS_LINK else None,
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

    if gm_feedback.token is not None:
        # The only way back to anonymous feedback is its private link.
        return redirect("survey-gm-feedback", survey.pk, gm_feedback.token)
    return redirect("survey-detail", survey.pk)


@verified_required
def gm_feedback_detail(
    request: AuthHttpRequest, survey_pk: int, token: uuid.UUID
) -> HttpResponse:
    # The token is the credential: there's no ownership check, since anonymous
    # feedback has no owner to check against.
    gm_feedback = get_object_or_404(
        GMFeedback.objects.select_related("survey__semester"),
        survey=survey_pk,
        token=token,
    )
    return render(
        request,
        "surveys/gm_feedback_detail.html",
        {"survey": gm_feedback.survey, "gm_feedback": gm_feedback},
    )


def _inbox_params(status: str, page: int = 1) -> str:
    """The query string (no leading "?") holding an inbox's settings."""
    params: dict[str, str] = {}
    if status != DEFAULT_STATUS:
        params["status"] = status
    if page > 1:
        params["page"] = str(page)
    return urlencode(params)


def _inbox_return_url(
    request: HttpRequest, url_name: str, survey_pk: int, status_filters: StatusFilters
) -> str:
    """Where a button in an inbox should land: the same filter and page.

    The target is rebuilt from the posted values rather than echoed back, so a
    forged form can only ever point at this inbox.
    """
    status = request.POST.get("back_status", "")
    if status not in status_filters:
        status = DEFAULT_STATUS
    try:
        page = int(request.POST.get("back_page", ""))
    except ValueError:
        page = 1
    params = _inbox_params(status, page)
    url = reverse(url_name, args=[survey_pk])
    return f"{url}?{params}" if params else url


class _Inbox[M: models.Model](ListView[M]):
    """Responses to one survey, oldest first, filtered on whether they're read.

    Oldest first so they're read in the order they came in, which helps when
    responding to them. Unread is the default filter, since that's what there is
    to do; the dropdown switches to everything. Opening the inbox never marks
    anything read: that only happens by pressing a button.
    """

    survey: Survey
    status: str
    paginate_by = RESPONSES_PER_PAGE
    url_name: str
    status_filters: StatusFilters

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any):
        super().setup(request, *args, **kwargs)
        self.survey = get_object_or_404(
            Survey.objects.select_related("semester"), pk=self.kwargs["survey_pk"]
        )
        status = request.GET.get("status", "")
        self.status = status if status in self.status_filters else DEFAULT_STATUS

    def paginate_queryset(
        self, queryset: QuerySet[M], page_size: int
    ) -> tuple[Paginator[M], Page[M], QuerySet[M], bool]:
        # Marking a response read takes it out of the unread filter, so the page
        # the reader was on may no longer exist. Land on the last one, not a 404.
        paginator = self.get_paginator(queryset, page_size)
        page = paginator.get_page(self.request.GET.get("page"))
        return paginator, page, page.object_list, page.has_other_pages()  # type: ignore[return-value]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["survey"] = self.survey
        context["status"] = self.status
        context["status_label"] = self.status_filters[self.status][0]
        context["status_options"] = [
            {
                "label": label,
                "params": _inbox_params(value),
                "selected": value == self.status,
            }
            for value, (label, _) in self.status_filters.items()
        ]
        context["inbox_params"] = _inbox_params(self.status)
        context["inbox_url"] = reverse(self.url_name, args=[self.survey.pk])
        return context


class GMFeedbackInbox(AdminRequiredMixin, _Inbox[GMFeedback]):
    """Evan's inbox of GM feedback, where he marks it read or replies."""

    template_name = "surveys/gm_feedback_inbox.html"
    url_name = "survey-gm-feedback-inbox"
    status_filters = REPLY_FILTERS

    def get_queryset(self) -> QuerySet[GMFeedback]:
        return (
            GMFeedback.objects.filter(survey=self.survey)
            .filter(self.status_filters[self.status][1])
            .select_related("student__user")
            .order_by("pk")
        )


class InstructorCommentInbox(StaffRequiredMixin, _Inbox[InstructorComment]):
    """An instructor's inbox of the comments their students left them."""

    template_name = "surveys/instructor_comment_inbox.html"
    url_name = "survey-instructor-comment-inbox"
    status_filters = READ_FILTERS

    def get_queryset(self) -> QuerySet[InstructorComment]:
        return (
            InstructorComment.objects.filter(
                survey=self.survey, assistant__user=self.request.user
            )
            .filter(self.status_filters[self.status][1])
            .select_related("student__user")
            .order_by("pk")
        )


@admin_required
@require_POST
def gm_feedback_respond(
    request: AuthHttpRequest, survey_pk: int, feedback_pk: int
) -> HttpResponse:
    """Marks GM feedback read or unread, or replies to it, which also marks it read."""
    feedback = get_object_or_404(GMFeedback, survey=survey_pk, pk=feedback_pk)
    action = request.POST.get("action")
    if action == "reply":
        if feedback.student is None and feedback.token is None:
            messages.error(request, "Nobody can see a reply to that feedback.")
        else:
            reply = request.POST.get("reply", "").strip()
            if reply != feedback.reply:
                feedback.reply = reply
                feedback.replied_at = timezone.now() if reply else None
            feedback.is_read = True
            feedback.save()
    elif action in ("read", "unread"):
        feedback.is_read = action == "read"
        feedback.save()
    else:
        messages.error(request, "Unknown action.")
    return redirect(
        _inbox_return_url(request, "survey-gm-feedback-inbox", survey_pk, REPLY_FILTERS)
    )


@staff_required
@require_POST
def instructor_comment_mark(
    request: AuthHttpRequest, survey_pk: int, comment_pk: int
) -> HttpResponse:
    """Marks a comment read or unread; only its own instructor can."""
    comment = get_object_or_404(
        InstructorComment,
        survey=survey_pk,
        pk=comment_pk,
        assistant__user=request.user,
    )
    action = request.POST.get("action")
    if action in ("read", "unread"):
        comment.is_read = action == "read"
        comment.save()
    else:
        messages.error(request, "Unknown action.")
    return redirect(
        _inbox_return_url(
            request, "survey-instructor-comment-inbox", survey_pk, READ_FILTERS
        )
    )
