"""Roster views

For historical reasons (aka I didn't plan ahead),
the division between dashboard and roster is a bit weird.

* roster handles the list of students and their curriculums
* roster also handles invoices
* dashboard handles stuff and uploads and pset submissions

So e.g. "list students by most recent pset" goes under dashboard.
"""

import collections
import datetime
import logging
from typing import Any, Dict, List, Optional

from allauth.socialaccount.models import SocialAccount
from braces.views import LoginRequiredMixin, StaffuserRequiredMixin
from core.models import Semester, Unit
from dashboard.models import PSet
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required  # NOQA
from django.contrib.auth.models import Group, User
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied  # NOQA
from django.db.models.expressions import F
from django.db.models.fields import FloatField
from django.db.models.functions.comparison import Cast
from django.db.models.manager import Manager
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect  # NOQA
from django.http.response import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic.edit import UpdateView
from django.views.generic.list import ListView
from evans_django_tools import ACTION_LOG_LEVEL, SUCCESS_LOG_LEVEL
from otisweb.decorators import admin_required
from otisweb.utils import AuthHttpRequest, mailchimp_subscribe
from prettytable import PrettyTable

from roster.utils import (
    can_edit,
    get_current_students,
    get_student_by_pk,
    infer_student,
)  # NOQA

from .forms import (
    AdvanceForm,
    CurriculumForm,
    DecisionForm,
    InquiryForm,
    UserForm,
)  # NOQA
from .models import (
    Invoice,
    RegistrationContainer,
    Student,
    StudentRegistration,
    UnitInquiry,
)  # NOQA

# Create your views here.

logger = logging.getLogger(__name__)


@login_required
def username_lookup(request: HttpRequest, username: str) -> HttpResponse:
    queryset = Student.objects.filter(user__username=username).order_by(
        "-semester__end_year"
    )
    if (student := queryset.first()) is not None:
        return HttpResponseRedirect(student.get_absolute_url())
    else:
        raise Http404(f"No student attached to the user {username}")


@login_required
def curriculum(request: HttpRequest, student_pk: int) -> HttpResponse:
    student = get_student_by_pk(request, student_pk)
    units = Unit.objects.filter(group__hidden=False)
    original = student.curriculum.values_list("pk", flat=True)

    enabled = can_edit(request, student) or student.newborn
    if request.method == "POST" and enabled:
        form = CurriculumForm(request.POST, units=units, enabled=True)
        if form.is_valid():
            data = form.cleaned_data
            # get groups with nonempty unit sets
            unit_lists = [
                data[k] for k in data if k.startswith("group-") and data[k] is not None
            ]
            values = [unit for unit_list in unit_lists for unit in unit_list]
            student.curriculum.set(values)
            student.save()
            messages.success(
                request, f"Successfully saved curriculum of {len(values)} units."
            )
    else:
        form = CurriculumForm(units=units, original=original, enabled=enabled)
        if not enabled:
            messages.info(
                request,
                "You can't edit this curriculum " + "since you are not an instructor.",
            )

    context = {
        "title": "Units for " + student.name,
        "student": student,
        "form": form,
        "enabled": enabled,
    }
    return render(request, "roster/currshow.html", context)


@login_required
@require_POST
def finalize(request: HttpRequest, student_pk: int) -> HttpResponse:
    # Removes a newborn status, thus activating everything
    student = get_student_by_pk(request, student_pk)
    if student.curriculum.count() > 0:
        student.newborn = False
        first_units = student.curriculum.all()[0:3]
        student.unlocked_units.set(first_units)
        student.save()
        messages.success(
            request,
            "Your curriculum has been finalized! "
            "You can start working now; "
            "the first three units have been unlocked.",
        )
    else:
        messages.error(
            request,
            "You didn't select any units. "
            "You should select some units before using this link.",
        )
    return HttpResponseRedirect(reverse("portal", args=(student_pk,)))


@login_required
def advance(request: HttpRequest, student_pk: int) -> Any:
    student = get_student_by_pk(request, student_pk, requires_edit=True)
    if request.method == "POST":
        form = AdvanceForm(request.POST, student=student)
        if form.is_valid():
            data = form.cleaned_data
            student.unlocked_units.add(*data["units_to_unlock"])
            student.curriculum.add(*data["units_to_unlock"])
            student.curriculum.add(*data["units_to_add"])
            student.unlocked_units.remove(*data["units_to_lock"])
            student.unlocked_units.remove(*data["units_to_drop"])
            student.curriculum.remove(*data["units_to_drop"])
            student.save()
            messages.success(request, "Successfully updated student.")
            form = AdvanceForm(student=student)
            # uncomment the below if you want to load the portal again
            # return HttpResponseRedirect(reverse("portal", args=(student_pk,)))
    else:
        form = AdvanceForm(student=student)

    context: Dict[str, Any] = {"title": "Advance " + student.name}
    context["form"] = form
    context["student"] = student
    context["curriculum"] = student.generate_curriculum_rows()
    if student.semester.uses_legacy_pset_system:
        uploads = student.uploadedfile_set  # type: ignore
        context["num_psets"] = (
            uploads.filter(category="psets").values("unit").distinct().count()
        )
    else:
        context["num_psets"] = PSet.objects.filter(student=student).count()

    return render(request, "roster/advance.html", context)


@login_required
def invoice(request: HttpRequest, student_pk: Optional[int] = None) -> HttpResponse:
    if student_pk is None:
        student = infer_student(request)
        return HttpResponseRedirect(reverse("invoice", args=(student.pk,)))

    # Now assume student_pk is not None
    student = get_student_by_pk(request, student_pk, payment_exempt=True)

    try:
        invoice: Optional[Invoice] = student.invoice
    except ObjectDoesNotExist:
        invoice = None

    context = {
        "title": "Invoice for " + student.name,
        "student": student,
        "invoice": invoice,
        "checksum": student.get_checksum(settings.INVOICE_HASH_KEY),
    }
    # return HttpResponse("hi")
    return render(request, "roster/invoice.html", context)


@staff_member_required
def master_schedule(request: HttpRequest) -> HttpResponse:
    student_names_and_unit_pks = (
        get_current_students()
        .filter(legit=True)
        .values("pk", "user__first_name", "user__last_name", "curriculum")
    )
    unit_to_student_dicts = collections.defaultdict(list)
    for d in student_names_and_unit_pks:
        # e.g. d = {'name': Student, 'curriculum': 30}
        unit_to_student_dicts[d["curriculum"]].append(
            {
                "short_name": d["user__first_name"] + " " + d["user__last_name"][0:1],
                "full_name": d["user__first_name"] + " " + d["user__last_name"],
                "pk": d["pk"],
            }
        )

    chart: List[Dict[str, Any]] = []
    unit_dicts = Unit.objects.order_by("position").values(
        "position", "pk", "group__subject", "group__name", "code"
    )
    for unit_dict in unit_dicts:
        row = dict(unit_dict)
        row["student_dicts"] = unit_to_student_dicts[unit_dict["pk"]]
        chart.append(row)
    semester = Semester.objects.get(active=True)
    context = {"chart": chart, "title": "Master Schedule", "semester": semester}
    return render(request, "roster/master_schedule.html", context)


class UpdateInvoice(
    LoginRequiredMixin,
    StaffuserRequiredMixin,
    UpdateView[Invoice, BaseModelForm[Invoice]],
):
    model = Invoice
    fields = (
        "preps_taught",
        "hours_taught",
        "adjustment",
        "extras",
        "total_paid",
        "memo",
    )
    object: Invoice

    def get_success_url(self):
        return reverse("invoice", args=(self.object.student.pk,))


# Inquiry views
@login_required
def inquiry(request: AuthHttpRequest, student_pk: int) -> HttpResponse:
    student = get_student_by_pk(request, student_pk)
    if not student.semester.active:
        raise PermissionDenied(
            "Not an active semester, so change petitions are no longer possible."
        )
    if student.is_delinquent:
        raise PermissionDenied("Student is delinquent")
    if not student.enabled:
        raise PermissionDenied("Student account not enabled")
    if student.newborn:
        raise PermissionDenied(
            "This form isn't enabled yet because you have not chosen your initial units."
        )

    context: Dict[str, Any] = {}
    current_inquiries = UnitInquiry.objects.filter(student=student)

    # Create form for submitting new inquiries
    if request.method == "POST":
        form = InquiryForm(request.POST, student=student)
        if form.is_valid():
            inquiry = form.save(commit=False)
            inquiry.student = student
            # check if exists already and created recently
            if UnitInquiry.objects.filter(
                unit=inquiry.unit,
                student=student,
                action_type=inquiry.action_type,
                created_at__gte=timezone.now() - datetime.timedelta(seconds=90),
                status="INQ_NEW",
            ).exists():
                messages.warning(
                    request,
                    "The same petition already was "
                    "submitted within the last 90 seconds.",
                )
            else:
                inquiry.save()

                num_past_unlock_inquiries = current_inquiries.filter(
                    action_type="INQ_ACT_UNLOCK"
                ).count()
                unlocked_count = (
                    current_inquiries.filter(
                        action_type="INQ_ACT_UNLOCK", status="INQ_NEW"
                    ).count()
                    + student.unlocked_units.count()
                )

                # auto reject criteria
                auto_reject_criteria = (
                    inquiry.action_type == "INQ_ACT_UNLOCK" and unlocked_count > 9
                )

                # auto hold criteria
                num_psets = PSet.objects.filter(student=student).count()
                auto_hold_criteria = num_past_unlock_inquiries > (
                    10 + 1.5 * num_psets**1.2
                )

                # auto-acceptance criteria
                auto_accept_criteria = inquiry.action_type == "INQ_ACT_APPEND"
                auto_accept_criteria |= (
                    num_past_unlock_inquiries <= 6
                    and unlocked_count < 9
                    and (not auto_hold_criteria and not auto_reject_criteria)
                )

                if auto_reject_criteria and not request.user.is_staff:
                    inquiry.status = "INQ_REJ"
                    inquiry.save()
                    messages.error(
                        request,
                        "You can't have more than 9 unfinished units unlocked at once.",
                    )
                elif auto_accept_criteria or request.user.is_staff:
                    inquiry.run_accept()
                    messages.success(request, "Petition automatically processed.")
                elif auto_hold_criteria:
                    inquiry.status = "INQ_HOLD"
                    inquiry.save()
                    messages.warning(
                        request,
                        "You have submitted an abnormally large number of petitions "
                        + "so you should contact Evan specially to explain why.",
                    )
                else:
                    messages.success(request, "Petition submitted, wait for it!")
    else:
        form = InquiryForm(student=student)
    context["form"] = form

    context["inquiries"] = UnitInquiry.objects.filter(student=student)
    context["student"] = student
    context["curriculum"] = student.generate_curriculum_rows()

    return render(request, "roster/inquiry.html", context)


@login_required
def register(request: AuthHttpRequest) -> HttpResponse:
    try:
        container = RegistrationContainer.objects.get(semester__active=True)
    except (
        RegistrationContainer.DoesNotExist,
        RegistrationContainer.MultipleObjectsReturned,
    ):
        return HttpResponse("There isn't a currently active OTIS semester.", status=503)

    semester: Semester = container.semester
    if StudentRegistration.objects.filter(
        user=request.user, container=container
    ).exists():
        messages.info(
            request, message="You have already submitted a decision form for this year!"
        )
        form = None
    elif request.method == "POST":
        form = DecisionForm(request.POST, request.FILES)
        if form.is_valid():
            passcode = form.cleaned_data["passcode"]
            if passcode.lower() != container.passcode.lower():
                messages.error(request, message="Wrong passcode")
            elif form.cleaned_data.get(
                "track", "C"
            ) not in container.allowed_tracks.split(","):
                messages.error(
                    request,
                    message="That track is not currently accepting registrations.",
                )
            else:
                registration = form.save(commit=False)
                registration.container = container
                registration.user = request.user
                registration.save()
                request.user.first_name = form.cleaned_data["given_name"].strip()
                request.user.last_name = form.cleaned_data["surname"].strip()
                request.user.email = form.cleaned_data["email_address"]
                group, _ = Group.objects.get_or_create(name="Verified")
                group.user_set.add(request.user)  # type: ignore
                request.user.save()
                mailchimp_subscribe(request)
                messages.success(request, message="Submitted! Sit tight.")
                logger.log(
                    ACTION_LOG_LEVEL,
                    f"New registration from {request.user.get_full_name()}",
                    extra={"request": request},
                )
                return HttpResponseRedirect(reverse("index"))
    else:
        if container.allowed_tracks:
            initial_data_dict = {}
            most_recent_reg = (
                StudentRegistration.objects.filter(
                    user=request.user,
                )
                .order_by("-pk")
                .first()
            )
            if most_recent_reg is not None:
                for k in (
                    "parent_email",
                    "graduation_year",
                    "school_name",
                    "aops_username",
                    "gender",
                ):
                    initial_data_dict[k] = getattr(most_recent_reg, k)
            form = DecisionForm(initial=initial_data_dict)
        else:
            messages.warning(
                request,
                message="The currently active semester isn't accepting registrations right now.",
            )
            form = None
    context = {
        "title": f"{semester} Decision Form",
        "form": form,
        "container": container,
    }
    return render(request, "roster/decision_form.html", context)


@login_required
def update_profile(request: AuthHttpRequest) -> HttpResponse:
    old_email = request.user.email
    if request.method == "POST":
        form = UserForm(request.POST, instance=request.user)
        if form.is_valid():
            new_email = form.cleaned_data["email"]
            user: User = form.save()
            if old_email != new_email:
                logger.log(
                    SUCCESS_LOG_LEVEL,
                    f"User {user.get_full_name()} switched to {new_email}",
                    extra={"request": request},
                )
                user.save()
                mailchimp_subscribe(request)
            else:
                user.save()
            messages.success(request, "Your information has been updated.")
    else:
        form = UserForm(instance=request.user)
    context = {"form": form}
    return render(request, "roster/update_profile.html", context)


# TODO ugly hack but I'm tired of answering this request
@login_required
def unlock_rest_of_mystery(request: HttpRequest, delta: int = 1) -> HttpResponse:
    student = infer_student(request)
    assert delta == 1 or delta == 2
    try:
        mystery = student.unlocked_units.get(group__name="Mystery")
    except Unit.DoesNotExist:
        return HttpResponse(
            f"You don't have the Mystery unit unlocked!\nYou are currently {student}",
            status=403,
        )
    added_unit = get_object_or_404(Unit, position=mystery.position + delta)
    student.unlocked_units.remove(mystery)
    student.curriculum.remove(mystery)
    student.unlocked_units.add(added_unit)
    student.curriculum.add(added_unit)
    messages.success(request, f"Added the unit {added_unit}")
    return HttpResponseRedirect("/")


@admin_required
def giga_chart(request: HttpRequest, format_as: str) -> HttpResponse:
    queryset = Invoice.objects.filter(student__legit=True)
    queryset = queryset.filter(student__semester__active=True)
    queryset = queryset.select_related(
        "student__user",
        "student__reg",
        "student__semester",
        "student__user__profile",
    )
    queryset = queryset.prefetch_related("student__user__socialaccount_set")
    queryset = queryset.annotate(
        owed=Cast(
            F("student__semester__prep_rate") * F("preps_taught")
            + F("student__semester__hour_rate") * F("hours_taught")
            + F("adjustment")
            + F("extras")
            - F("total_paid")
            - F("credits"),
            FloatField(),
        )
    )
    queryset = queryset.annotate(
        debt=Cast(F("owed") / (F("owed") + F("total_paid") + 1e-8), FloatField())
    )

    queryset = queryset.order_by(
        "student__enabled",
        "debt",
        "student__first_name",
    )
    timestamp = timezone.now().strftime("%Y-%m-%d-%H%M%S")

    if settings.TESTING is True:
        where = "test"
    elif settings.DEBUG is True:
        where = "debug"
    else:
        where = "prod"
    rows = []
    header_row = [
        "pk",
        "Username",
        "Discord",
        "Name",
        "Enabled",
        "Debt%",
        # 'Track',
        "Last login (days)",
        "Grade",
        "Gender",
        "Country",
        "AoPS",
        "Student email",
        "Parent email",
        "Owed",
        # 'Preps',
        # 'Hours',
        "Adjustment",
        "Credits",
        "Extras",
        "Total Paid",
        "Forgive",
    ]  # header row

    for invoice in queryset:
        student = invoice.student
        user = student.user
        if user is None:
            continue
        reg = student.reg
        delta = timezone.now() - user.profile.last_seen
        days_since_last_seen = round(delta.total_seconds() / (3600 * 24), ndigits=2)
        socials: Manager[SocialAccount] = student.user.socialaccount_set  # type:ignore

        rows.append(
            [
                student.pk,
                user.username,
                "; ".join(
                    f"{d.extra_data['username']}#{d.extra_data['discriminator']}"
                    for d in socials.filter(provider__iexact="Discord")
                ),
                student.name,
                "Enabled" if student.enabled else "Disabled",
                f"{invoice.debt:.2f}",  # type: ignore
                # student.track,
                days_since_last_seen,
                reg.grade if reg is not None else "",
                reg.get_gender_display() if reg is not None else "",
                reg.country if reg is not None else "",
                reg.aops_username if reg is not None else "",
                user.email,
                reg.parent_email if reg is not None else "",
                round(invoice.total_owed),
                # invoice.preps_taught,
                # invoice.hours_taught,
                round(invoice.adjustment),
                round(invoice.credits),
                round(invoice.extras),
                round(invoice.total_paid),
            ]
        )

    pt = PrettyTable()
    pt.field_names = header_row
    title = f"OTIS Gigi-Chart ({where}) generated {timestamp}"
    for row in rows:
        pt.add_row(row)

    format_as = format_as.lower()
    if format_as == "csv":
        filename = f"otis-{where}-{timestamp}.csv"
        response = HttpResponse(
            content=pt.get_csv_string(),
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    elif format_as == "plain":
        response = HttpResponse(pt.get_string(title=title))
    elif format_as == "html":
        response = HttpResponse(pt.get_html_string(title=title))
    else:
        raise NotImplementedError(f"Format {format_as} not implemented yet")

    return response


class StudentAssistantList(StaffuserRequiredMixin, ListView[Student]):
    model = Student
    template_name = "roster/student_assistant_list.html"
    context_object_name = "students"

    def get_queryset(self) -> QuerySet[Student]:
        qs = Student.objects.filter(
            semester__active=True,
            assistant__isnull=False,
            enabled=True,
        )
        qs = qs.select_related("user", "assistant", "assistant__user")
        qs = qs.order_by("assistant__shortname", "user__first_name", "user__last_name")
        return qs

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        qs1 = Student.objects.filter(semester__active=True, assistant__isnull=False)
        qs1 = qs1.select_related("assistant__user")
        pks1 = qs1.values_list("assistant__user__pk", flat=True)
        group, _ = Group.objects.get_or_create(name="Active Staff")
        qs2: QuerySet[User] = group.user_set.all()  # type: ignore
        pks2 = qs2.values_list("pk", flat=True)
        context["needs_sync"] = set(pks1) != set(pks2)
        return context

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not isinstance(request.user, User) or not request.user.is_superuser:
            raise PermissionDenied("Need admin rights to run this POST request.")
        group, _ = Group.objects.get_or_create(name="Active Staff")
        qs = Student.objects.filter(semester__active=True, assistant__isnull=False)
        qs = qs.select_related("assistant__user")
        pks = qs.values_list("assistant__user__pk", flat=True)
        group.user_set.set(pks)  # type: ignore
        messages.success(request, "Synced active staff group!")
        return super().get(request, *args, **kwargs)
