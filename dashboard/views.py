# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from braces.views import LoginRequiredMixin
from core.models import Semester, Unit, UserProfile
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.db.models import Count, OuterRef, Subquery
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http import HttpResponse, HttpResponseRedirect
from django.http.request import HttpRequest
from django.http.response import HttpResponseBase
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import DetailView, ListView
from django.views.generic.edit import DeleteView, UpdateView
from evans_django_tools import VERBOSE_LOG_LEVEL
from exams.models import PracticeExam
from markets.models import Market
from otisweb.utils import (
    AuthHttpRequest,
    get_days_since,
    get_mailchimp_campaigns,
)  # NOQA
from roster.models import RegistrationContainer, Student, StudentRegistration
from roster.utils import (
    can_view,
    get_student_by_id,
    get_visible_students,
    infer_student,
)  # NOQA
from rpg.levelsys import (
    annotate_student_queryset_with_scores,
    check_level_up,
    get_level_info,
    get_student_rows,
)  # NOQA

from dashboard.forms import NewUploadForm, PSetResubmitForm, PSetSubmitForm
from dashboard.models import PSet, SemesterDownloadFile, UploadedFile  # NOQA
from dashboard.utils import get_units_to_submit, get_units_to_unlock  # NOQA

logger = logging.getLogger(__name__)


@login_required
def portal(request: AuthHttpRequest, student_id: int) -> HttpResponse:
    student = get_student_by_id(request, student_id, payment_exempt=True)
    if not request.user.is_staff and student.is_delinquent and not student.enabled:
        return HttpResponseRedirect(reverse("invoice", args=(student_id,)))
    semester = student.semester
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    student_profile, _ = UserProfile.objects.get_or_create(user=student.user)

    level_info = get_level_info(student)
    if request.user == student.user:
        result = check_level_up(student)
        if result is True and profile.show_bars is True:
            lvl = level_info["level_number"]
            messages.success(request, f"You leveled up! You're now level {lvl}.")

    context: Dict[str, Any] = {}
    context["title"] = f"{student.name} ({semester.name})"
    context["last_seen"] = student_profile.last_seen
    context["student"] = student
    context["reg"] = student.reg
    context["semester"] = semester
    context["history"] = (
        Student.objects.filter(user=student.user)
        .order_by("semester__end_year")
        .values("pk", "semester__end_year")
    )
    context["profile"] = profile

    context["curriculum"] = student.generate_curriculum_rows()
    context["tests"] = PracticeExam.objects.filter(
        is_test=True, family=semester.exam_family, due_date__isnull=False
    )
    context["quizzes"] = PracticeExam.objects.filter(
        is_test=False, family=semester.exam_family, due_date__isnull=False
    )
    context["emails"] = [
        e
        for e in get_mailchimp_campaigns(14)
        if e["timestamp"] >= profile.last_email_dismiss
    ]
    context["downloads"] = SemesterDownloadFile.objects.filter(
        semester=semester,
        created_at__gte=profile.last_download_dismiss,
    ).filter(
        created_at__gte=timezone.now() - timedelta(days=14),
    )
    context["markets"] = Market.active.all()
    context["num_sem_downloads"] = SemesterDownloadFile.objects.filter(
        semester=semester
    ).count()

    context.update(level_info)
    return render(request, "dashboard/portal.html", context)


def certify(
    request: HttpRequest,
    student_id: Optional[int] = None,
    checksum: Optional[str] = None,
):
    if student_id is None:
        student = infer_student(request)
    else:
        student = get_object_or_404(Student, pk=student_id)
    if checksum is None:
        if can_view(request, student):
            checksum = student.get_checksum(settings.CERT_HASH_KEY)
            return HttpResponseRedirect(reverse("certify", args=(student.id, checksum)))
        else:
            raise PermissionDenied("Not authorized to generate checksum")
    elif checksum != student.get_checksum(settings.CERT_HASH_KEY):
        raise PermissionDenied("Wrong hash")
    else:
        level_info = get_level_info(student)
        context = {
            "student": student,
            "hearts": level_info["meters"]["hearts"].value,
            "level_number": level_info["level_number"],
            "level_name": level_info["level_name"],
            "checksum": student.get_checksum(settings.CERT_HASH_KEY),
            "target_url": f"{request.scheme}//{request.get_host()}"
            + reverse("certify", args=(student.id, checksum)),
        }
        return render(request, "dashboard/certify.html", context)


class PSetQueueList(LoginRequiredMixin, ListView[PSet]):
    template_name = "dashboard/pset_queue_list.html"

    def get_queryset(self) -> QuerySet[PSet]:
        return PSet.objects.filter(
            status__in=("P", "PA", "PR"),
            student__semester__active=True,
        ).order_by("pk")


@login_required
def submit_pset(request: HttpRequest, student_id: int) -> HttpResponse:
    student = get_student_by_id(request, student_id)
    if student.semester.active is False:
        raise PermissionDenied("Not an active semester")
    if student.enabled is False:
        raise PermissionDenied("Not enabled")
    if student.is_delinquent:
        raise PermissionDenied("Student is delinquent")

    if request.method == "POST":
        form = PSetSubmitForm(request.POST, request.FILES)
    else:
        form = PSetSubmitForm()

    form.fields["unit"].queryset = get_units_to_submit(student)  # type: ignore
    form.fields["next_unit_to_unlock"].queryset = get_units_to_unlock(student)  # type: ignore
    if request.method == "POST" and form.is_valid():
        pset = form.save(commit=False)
        if PSet.objects.filter(student=student, unit=pset.unit).exists():
            messages.error(
                request,
                "You have already submitted for this unit. "
                "If this is intentional, you should use the resubmit button "
                "at the bottom of this page instead.",
            )
        else:
            f = UploadedFile(
                benefactor=student,
                owner=student.user,
                category="psets",
                description="",
                content=form.cleaned_data["content"],
                unit=pset.unit,
            )
            f.save()
            pset.student = student
            pset.upload = f
            pset.save()
            messages.success(
                request,
                "The problem set is submitted successfully " "and is pending review!",
            )
            logger.log(
                VERBOSE_LOG_LEVEL,
                f"{student} submitted for {pset.unit}",
                extra={"request": request},
            )
            return HttpResponseRedirect(pset.get_absolute_url())

    psets = PSet.objects.filter(student=student).order_by("-upload__created_at")
    context = {
        "title": "Ready to submit?",
        "student": student,
        "unaccepted_psets": psets.exclude(status="A"),
        "form": form,
    }
    return render(request, "dashboard/submit_pset_form.html", context)


class StudentPSetList(LoginRequiredMixin, ListView[PSet]):
    template_name = "dashboard/student_pset_list.html"

    def get_queryset(self) -> QuerySet[PSet]:
        return PSet.objects.filter(student=self.student).order_by("-upload__created_at")

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["student"] = self.student
        return context

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        if not isinstance(request.user, User):
            return super().dispatch(request, *args, **kwargs)  # login required mixin

        self.student = get_object_or_404(Student, pk=kwargs.pop("student_id"))
        if not can_view(request, self.student):
            raise PermissionDenied(
                "You do not have permission to view this student's problem sets"
            )
        if self.student.is_delinquent:
            raise PermissionDenied("Student is delinquent")

        return super().dispatch(request, *args, **kwargs)


@login_required
def resubmit_pset(request: HttpRequest, pk: int) -> HttpResponse:
    pset = get_object_or_404(PSet, pk=pk)
    student = pset.student
    if not can_view(request, student):
        raise PermissionDenied("You are missing privileges for this problem set")

    if pset.status == "R":
        verb = "Replace"
    elif pset.status == "A":
        verb = "Add to"
    else:
        assert pset.status in ("PA", "PR", "P")
        verb = "Update"

    if request.method == "POST":
        form = PSetResubmitForm(request.POST, request.FILES, instance=pset)
    else:
        form = PSetResubmitForm(instance=pset)
    if pset.status in ("A", "PA"):
        form.fields.pop("next_unit_to_unlock")
    else:
        form.fields["next_unit_to_unlock"].queryset = get_units_to_unlock(student)  # type: ignore

    if request.method == "POST" and form.is_valid():
        pset = form.save(commit=False)
        if pset.upload is None:
            raise SuspiciousOperation("There was no uploaded file")
        pset.upload.content = form.cleaned_data["content"]
        pset.upload.save()
        if pset.rejected:
            pset.status = "PR"
        elif pset.accepted:
            pset.status = "PA"
        pset.save()
        messages.success(
            request,
            "The problem set is submitted successfully " "and is pending review!",
        )
        logger.log(
            VERBOSE_LOG_LEVEL,
            f"{student} re-submitted {pset.unit}",
            extra={"request": request},
        )
        return HttpResponseRedirect(pset.get_absolute_url())

    context = {
        "title": f"{verb} {pset.filename or pset.pk}",
        "student": student,
        "pset": pset,
        "form": form,
    }
    return render(request, "dashboard/resubmit_pset_form.html", context)


@login_required
def uploads(request: HttpRequest, student_id: int, unit_id: int) -> HttpResponse:
    student = get_student_by_id(request, student_id)
    unit = get_object_or_404(Unit, id=unit_id)
    uploads = UploadedFile.objects.filter(benefactor=student, unit=unit)
    if not student.check_unit_unlocked(unit) and not uploads.exists():
        raise PermissionDenied("This unit is not unlocked yet")

    form = None
    if request.method == "POST":
        form = NewUploadForm(request.POST, request.FILES)
        if form.is_valid():
            new_upload = form.save(commit=False)
            new_upload.unit = unit
            new_upload.benefactor = student
            new_upload.owner = request.user
            new_upload.save()
            messages.success(request, "New file has been uploaded.")
            form = None  # clear form on successful upload, prevent duplicates
    if form is None:
        form = NewUploadForm(initial={"unit": unit})

    context: Dict[str, Any] = {}
    context["title"] = "File Uploads"
    context["student"] = student
    context["unit"] = unit
    context["form"] = form
    context["files"] = uploads
    # TODO form for adding new files
    return render(request, "dashboard/uploads.html", context)


@login_required
def index(request: AuthHttpRequest) -> HttpResponse:
    students = get_visible_students(request.user, current=True)
    if len(students) == 1:  # unique match
        student = students.first()
        assert student is not None
        return HttpResponseRedirect(reverse("portal", args=(student.id,)))
    queryset = annotate_student_queryset_with_scores(students).order_by(
        "track", "user__first_name", "user__last_name"
    )
    context: Dict[str, Any] = {}
    context["title"] = "Current year listing"
    context["rows"] = get_student_rows(queryset)
    context["stulist_show_semester"] = False
    context["submitted_registration"] = StudentRegistration.objects.filter(
        user=request.user, container__semester__active=True
    ).exists()
    context["exists_registration"] = RegistrationContainer.objects.filter(
        semester__active=True,
    ).exists()
    return render(request, "dashboard/stulist.html", context)


@login_required
def past(request: AuthHttpRequest, semester_id: Optional[int] = None):
    students = get_visible_students(request.user, current=False)
    if semester_id is not None:
        semester = get_object_or_404(Semester, pk=semester_id)
        students = students.filter(semester=semester)
    else:
        semester = None
    queryset = annotate_student_queryset_with_scores(students).order_by(
        "track", "user__first_name", "user__last_name"
    )
    context: Dict[str, Any] = {}
    context["title"] = "Previous year listing"
    context["rows"] = get_student_rows(queryset)
    context["past"] = True
    if semester is not None:
        context["semester"] = semester
        context["stulist_show_semester"] = False
    else:
        context["stulist_show_semester"] = True
    return render(request, "dashboard/stulist.html", context)


class SemesterList(LoginRequiredMixin, ListView[Semester]):
    model = Semester
    template_name = "dashboard/semlist.html"

    def get_queryset(self) -> QuerySet[Semester]:
        queryset = super().get_queryset()
        queryset = queryset.annotate(count=Count("student"))  # type: ignore
        return queryset  # type: ignore


class UpdateFile(
    LoginRequiredMixin, UpdateView[UploadedFile, BaseModelForm[UploadedFile]]
):
    model = UploadedFile
    fields = (
        "category",
        "content",
        "description",
    )
    object: UploadedFile

    def get_success_url(self):
        stu_id = self.object.benefactor.id
        unit_id = self.object.unit.id if self.object.unit is not None else 0
        return reverse(
            "uploads",
            args=(
                stu_id,
                unit_id,
            ),
        )

    def get_object(self, *args: Any, **kwargs: Any) -> UploadedFile:
        obj = super().get_object(*args, **kwargs)
        is_staff = getattr(self.request.user, "is_staff", False)
        if obj.owner != self.request.user and is_staff is False:
            raise PermissionDenied("Not authorized to update this file")
        return obj


class DeleteFile(LoginRequiredMixin, DeleteView):
    model = UploadedFile
    success_url = reverse_lazy("index")

    def get_object(self, *args: Any, **kwargs: Any) -> UploadedFile:
        obj = super().get_object(*args, **kwargs)
        if not obj.owner == self.request.user and getattr(
            self.request.user, "is_staff", False
        ):
            raise PermissionDenied("Not authorized to delete this file")
        return obj


@staff_member_required
def idlewarn(request: AuthHttpRequest) -> HttpResponse:
    context: Dict[str, Any] = {}
    context["title"] = "Idle-warn"

    newest_qset = UploadedFile.objects.filter(
        category="psets", benefactor=OuterRef("pk")
    )
    newest = newest_qset.order_by("-created_at").values("created_at")[:1]

    queryset = annotate_student_queryset_with_scores(
        get_visible_students(request.user).filter(legit=True)
    )
    queryset = queryset.annotate(latest_pset=Subquery(newest))  # type: ignore
    rows = get_student_rows(queryset)
    for row in rows:
        row["days_since_last_seen"] = get_days_since(row["last_seen"])
        row["days_since_last_pset"] = get_days_since(row["student"].latest_pset)
    rows.sort(
        key=lambda row: (
            not row["student"].newborn,
            -(row["days_since_last_pset"] or 1e9),
            -(row["days_since_last_seen"] or 1e9),
            row["level"],
        )
    )
    context["rows"] = rows

    return render(request, "dashboard/idlewarn.html", context)


class DownloadList(LoginRequiredMixin, ListView[SemesterDownloadFile]):
    template_name = "dashboard/download_list.html"

    def get_queryset(self) -> QuerySet[SemesterDownloadFile]:
        student = get_student_by_id(self.request, self.kwargs["pk"])
        return SemesterDownloadFile.objects.filter(semester=student.semester)


class PSetDetail(LoginRequiredMixin, DetailView[PSet]):
    template_name = "dashboard/pset_detail.html"
    model = PSet
    object_name = "pset"

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        pset = self.get_object()
        if not can_view(request, pset.student):
            raise PermissionDenied("Can't view work by this student")
        return super(DetailView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["student"] = self.get_object().student
        return context
