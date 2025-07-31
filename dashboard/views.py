# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging
from typing import Any, Optional

from braces.views import LoginRequiredMixin
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Count, OuterRef, Subquery
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http import HttpResponse, HttpResponseRedirect
from django.http.request import HttpRequest
from django.http.response import HttpResponseBase
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import DeleteView, UpdateView

from core.models import Semester, Unit, UserProfile
from dashboard.forms import (
    BonusRequestForm,
    NewUploadForm,
    PSetResubmitForm,
    PSetSubmitForm,
)
from dashboard.models import PSet, SemesterDownloadFile, UploadedFile
from dashboard.utils import get_news, get_units_to_submit, get_units_to_unlock
from evans_django_tools import VERBOSE_LOG_LEVEL
from exams.models import PracticeExam
from otisweb.utils import AuthHttpRequest, get_days_since
from roster.models import RegistrationContainer, Student, StudentRegistration
from roster.utils import (  # NOQA
    can_view,
    get_student_by_pk,
    get_visible_students,
    infer_student,
)
from rpg.levelsys import (  # NOQA
    annotate_student_queryset_with_scores,
    check_level_up,
    get_level_info,
    get_student_rows,
)

logger = logging.getLogger(__name__)


@login_required
def portal(request: AuthHttpRequest, student_pk: int) -> HttpResponse:
    student = get_student_by_pk(request, student_pk, payment_exempt=True)
    if not request.user.is_staff and student.is_delinquent:
        return HttpResponseRedirect(reverse("invoice", args=(student_pk,)))
    semester = student.semester
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    student_profile, _ = UserProfile.objects.get_or_create(user=student.user)

    level_info = get_level_info(student)
    if request.user == student.user:
        result = check_level_up(student, level_info)
        if result is True and profile.show_bars is True:
            lvl = level_info["level_number"]
            messages.success(request, f"You leveled up! You're now level {lvl}.")

    context: dict[str, Any] = {
        "title": f"{student.name} ({semester.name})",
        "last_seen": student_profile.last_seen,
        "student": student,
        "reg": student.reg,
        "semester": semester,
        "history": Student.objects.filter(user=student.user)
        .order_by("semester__end_year")
        .values("pk", "semester__end_year"),
    }
    context["profile"] = profile

    context["curriculum"] = student.generate_curriculum_rows()
    context["tests"] = PracticeExam.objects.filter(
        is_test=True, family=semester.exam_family, due_date__isnull=False
    )
    context["quizzes"] = PracticeExam.objects.filter(
        is_test=False, family=semester.exam_family, due_date__isnull=False
    )
    context["num_sem_downloads"] = SemesterDownloadFile.objects.filter(
        semester=semester
    ).count()

    # notifications
    context["news"] = get_news(profile)
    context["num_news"] = sum(len(_) for _ in context["news"].values())  # type: ignore

    context |= level_info
    return render(request, "dashboard/portal.html", context)


def certify(
    request: HttpRequest,
    student_pk: Optional[int] = None,
    checksum: Optional[str] = None,
):
    if student_pk is None:
        student = infer_student(request)
    else:
        student = get_object_or_404(Student, pk=student_pk)
    if checksum is None:
        if not can_view(request, student):
            raise PermissionDenied("Not authorized to generate checksum")
        checksum = student.get_checksum(settings.CERT_HASH_KEY)
        return HttpResponseRedirect(reverse("certify", args=(student.pk, checksum)))
    elif checksum != student.get_checksum(settings.CERT_HASH_KEY):
        raise PermissionDenied("Wrong hash")
    else:
        level_info = get_level_info(student)
        clubs = level_info["meters"]["clubs"].value
        hearts = level_info["meters"]["hearts"].value
        if hearts <= 3 and clubs <= 20:
            letter_grade = "C"
        elif hearts <= 10 and clubs <= 50:
            letter_grade = "B"
        else:
            letter_grade = "A"

        semesters = [s.semester for s in Student.objects.filter(user=student.user)]
        assert semesters
        if len(semesters) == 1:
            years = f"{semesters[0].years} year"
        elif len(semesters) == 2:
            years = f"{semesters[0].years} and {semesters[1].years} years"
        else:
            years = (
                ", ".join(s.years for s in semesters[:-1])
                + ", and "
                + semesters[-1].years
                + " years"
            )

        context = {
            "student": student,
            "years": years,
            "hearts": hearts,
            "letter_grade": letter_grade,
            "level_number": level_info["level_number"],
            "level_name": level_info["level_name"],
            "checksum": student.get_checksum(settings.CERT_HASH_KEY),
            "target_url": f"{request.scheme}//{request.get_host()}"
            + reverse("certify", args=(student.pk, checksum)),
        }
        return render(request, "dashboard/certify.html", context)


class PSetQueueList(LoginRequiredMixin, ListView[PSet]):
    template_name = "dashboard/pset_queue_list.html"

    def get_queryset(self) -> QuerySet[PSet]:
        return PSet.objects.filter(
            status__in=("P", "PA", "PR"),
            student__semester__active=True,
        ).order_by("upload__created_at")


@login_required
def submit_pset(request: HttpRequest, student_pk: int) -> HttpResponse:
    student = get_student_by_pk(request, student_pk)
    if student.semester.active is False:
        raise PermissionDenied("Not an active semester")
    if student.enabled is False:
        raise PermissionDenied("Not enabled")
    if student.is_delinquent:
        if isinstance(request.user, User) and request.user.is_staff:
            messages.warning(request, "Student is delinquent")
        else:
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
                "The problem set is submitted successfully and is pending review!",
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

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["student"] = self.student
        return context

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        if not isinstance(request.user, User):
            return super().dispatch(request, *args, **kwargs)  # login required mixin

        self.student = get_object_or_404(Student, pk=kwargs.pop("student_pk"))
        if not can_view(request, self.student):
            raise PermissionDenied(
                "You do not have permission to view this student's problem sets"
            )
        if self.student.is_delinquent:
            if request.user.is_staff:
                messages.warning(request, "Student is delinquent")
            else:
                raise PermissionDenied("Student is delinquent")
        return super().dispatch(request, *args, **kwargs)


@login_required
def resubmit_pset(request: HttpRequest, pk: int) -> HttpResponse:
    pset = get_object_or_404(PSet, pk=pk)
    student = pset.student
    if student.semester.active is False:
        raise PermissionDenied("Not an active semester")
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
        if not form.cleaned_data["content"]:
            messages.info(
                request, "No file was provided so only the metadata will be changed."
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
            pset.upload = f
            pset.upload.save()
        if pset.rejected:
            pset.status = "PR"
        elif pset.accepted:
            pset.status = "PA"
        pset.save()
        messages.success(
            request,
            "The problem set is submitted successfully and is pending review!",
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
def uploads(request: HttpRequest, student_pk: int, unit_pk: int) -> HttpResponse:
    student = get_student_by_pk(request, student_pk)
    unit = get_object_or_404(Unit, pk=unit_pk)
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

    context: dict[str, Any] = {
        "title": "File Uploads",
        "student": student,
        "unit": unit,
        "form": form,
        "files": uploads,
    }
    # TODO form for adding new files
    return render(request, "dashboard/uploads.html", context)


@login_required
def bonus_level_request(request: HttpRequest, student_pk: int) -> HttpResponse:
    student = get_student_by_pk(request, student_pk)
    if student.semester.active is False:
        raise PermissionDenied("Not an active semester")

    level = student.last_level_seen
    if not Unit.objects.filter(group__bonuslevel__level__lte=level).exists():
        messages.error(request, "There are no secret units you can request yet.")

    if request.method == "POST":
        form = BonusRequestForm(request.POST, level=student.last_level_seen)
        if form.is_valid():
            new_unit = form.cleaned_data["unit"]
            student.curriculum.add(new_unit)
            messages.success(request, f"Added bonus unit {new_unit} for you.")
    else:
        form = BonusRequestForm(level=student.last_level_seen)
    context: dict[str, Any] = {"student": student, "form": form}
    return render(request, "dashboard/bonus_level_request.html", context)


@login_required
def index(request: AuthHttpRequest) -> HttpResponse:
    students = get_visible_students(request.user, current=True)
    if len(students) == 1:  # unique match
        student = students.first()
        assert student is not None
        return HttpResponseRedirect(reverse("portal", args=(student.pk,)))
    queryset = annotate_student_queryset_with_scores(students).order_by(
        "user__first_name", "user__last_name"
    )
    context: dict[str, Any] = {
        "title": "Current year listing",
        "rows": get_student_rows(queryset),
        "stulist_show_semester": False,
    }
    context["submitted_registration"] = StudentRegistration.objects.filter(
        user=request.user, container__semester__active=True
    ).exists()
    if context["submitted_registration"] is True:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        context["subscribed_to_reg_email"] = profile.email_on_registration_processed
    context["exists_registration"] = RegistrationContainer.objects.filter(
        semester__active=True,
    ).exists()
    return render(request, "dashboard/stulist.html", context)


@login_required
def past(request: AuthHttpRequest, semester_pk: Optional[int] = None):
    students = get_visible_students(request.user, current=False)
    if semester_pk is not None:
        semester = get_object_or_404(Semester, pk=semester_pk)
        students = students.filter(semester=semester)
    else:
        semester = None
    queryset = annotate_student_queryset_with_scores(students).order_by(
        "user__first_name", "user__last_name"
    )
    context: dict[str, Any] = {
        "title": "Previous year listing",
        "rows": get_student_rows(queryset),
        "past": True,
    }
    if semester is not None:
        context["semester"] = semester
        context["stulist_show_semester"] = False
    else:
        context["stulist_show_semester"] = True
    return render(request, "dashboard/stulist.html", context)


class SemesterList(LoginRequiredMixin, ListView[Semester]):
    model = Semester
    template_name = "dashboard/semester_list.html"

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

    def get_success_url(self) -> str:
        stu_pk: int = self.object.benefactor.pk
        unit_pk: int = self.object.unit.pk if self.object.unit is not None else 0
        return reverse(
            "uploads",
            args=(
                stu_pk,
                unit_pk,
            ),
        )

    def get_object(self, *args: Any, **kwargs: Any) -> UploadedFile:
        obj = super().get_object(*args, **kwargs)
        assert isinstance(self.request.user, User)
        if obj.owner != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("Not authorized to update this file")
        return obj


class DeleteFile(LoginRequiredMixin, DeleteView):
    model = UploadedFile
    success_url = reverse_lazy("index")

    def get_object(self, *args: Any, **kwargs: Any) -> UploadedFile:
        obj = super().get_object(*args, **kwargs)
        assert isinstance(self.request.user, User)
        if not self.request.user.is_staff:
            raise PermissionDenied("Not authorized to delete this file")
        return obj


@staff_member_required
def idlewarn(request: AuthHttpRequest) -> HttpResponse:
    context: dict[str, Any] = {"title": "Idle-warn"}
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
        student = get_student_by_pk(self.request, self.kwargs["pk"])
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

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["student"] = self.get_object().student
        return context
