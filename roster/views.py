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
from typing import Any, Optional

from allauth.socialaccount.models import SocialAccount
from braces.views import LoginRequiredMixin
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
)
from django.db.models.expressions import F
from django.db.models.fields import FloatField
from django.db.models.functions.comparison import Cast
from django.db.models.manager import Manager
from django.db.models.query import QuerySet
from django.forms import ValidationError
from django.forms.models import BaseModelForm
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.http.response import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic.edit import UpdateView
from django.views.generic.list import ListView
from django_discordo import SUCCESS_LOG_LEVEL
from prettytable import PrettyTable

from core.models import EMAIL_PREFERENCE_FIELDS, Semester, Unit, UserProfile
from dashboard.models import PSet
from otisweb.decorators import admin_required, staff_required
from otisweb.mixins import StaffRequiredMixin, VerifiedRequiredMixin
from otisweb.utils import AuthHttpRequest
from roster.forms import LinkAssistantForm
from roster.models import ApplyUUID, Assistant
from roster.utils import (
    can_edit,
    get_current_students,
    get_student_by_pk,
    infer_student,
)

from .forms import (
    AdvanceForm,
    CurriculumForm,
    DecisionForm,
    DiscordLookupForm,
    EmailLookupForm,
    InquiryForm,
    UserForm,
)
from .models import (
    Invoice,
    RegistrationContainer,
    Student,
    StudentRegistration,
    UnitInquiry,
    build_students,
)

# Create your views here.

logger = logging.getLogger(__name__)


@staff_required
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
        "title": f"Units for {student.name}",
        "student": student,
        "form": form,
        "enabled": enabled,
    }
    return render(request, "roster/currshow.html", context)


@login_required
def finalize(request: HttpRequest, student_pk: int) -> HttpResponse:
    if not request.method == "POST":
        raise PermissionDenied("Must use POST")
    # Removes a newborn status, thus activating everything
    student = get_student_by_pk(request, student_pk)
    if student.newborn is not True:
        raise PermissionDenied("Not allowed to call finalize more than once.")
    elif student.curriculum.count() > 0:
        student.newborn = False
        first_units = student.curriculum.all()[:3]
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
            student.unlocked_units.add(*data["units_to_open"])
            student.curriculum.add(*data["units_to_unlock"])
            student.curriculum.add(*data["units_to_open"])
            student.curriculum.add(*data["units_to_add"])
            student.unlocked_units.remove(*data["units_to_lock"])
            student.unlocked_units.remove(*data["units_to_drop"])
            student.curriculum.remove(*data["units_to_drop"])
            student.save()
            messages.success(request, "Successfully updated student.")
            form = AdvanceForm(student=student)
    else:
        form = AdvanceForm(student=student)

    context: dict[str, Any] = {
        "title": f"Advance {student.name}",
        "form": form,
        "student": student,
        "curriculum": student.generate_curriculum_rows(),
    }
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
        "title": f"Invoice for {student.name}",
        "student": student,
        "invoice": invoice,
        "render_as_past_year": (
            student.semester.active is False
            and Semester.objects.filter(active=True).exists()
        ),
        "checksum": student.get_checksum(settings.INVOICE_HASH_KEY),
    }
    return render(request, "roster/invoice.html", context)


@admin_required
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
                "short_name": d["user__first_name"] + " " + d["user__last_name"][:1],
                "full_name": d["user__first_name"] + " " + d["user__last_name"],
                "pk": d["pk"],
            }
        )

    chart: list[dict[str, Any]] = []
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
    StaffRequiredMixin,
    UpdateView[Invoice, BaseModelForm[Invoice]],
):
    model = Invoice
    fields = (
        "preps_taught",
        "hours_taught",
        "adjustment",
        "extras",
        "credits",
        "total_paid",
        "forgive_date",
        "memo",
    )
    object: Invoice

    def get_success_url(self):
        return reverse("invoice", args=(self.object.student.pk,))


def handle_inquiry(request: AuthHttpRequest, inquiry: UnitInquiry, student: Student):
    current_inquiries = UnitInquiry.objects.filter(student=student)
    inquiry.student = student
    # check if exists already and created recently
    if current_inquiries.filter(
        unit=inquiry.unit,
        action_type=inquiry.action_type,
        created_at__gte=timezone.now() - datetime.timedelta(seconds=90),
        status__in=("INQ_NEW", "INQ_ACC"),
    ).exists():
        messages.warning(
            request,
            "The same petition already was submitted within the last 90 seconds.",
        )
        return

    inquiry.save()

    # early auto accept criteria
    if inquiry.action_type == "INQ_ACT_APPEND" or request.user.is_staff:
        inquiry.run_accept()
        inquiry.was_auto_processed = True
        inquiry.save()
        messages.success(request, "Petition automatically processed.")
        return

    past_unlock_inquiries = current_inquiries.filter(action_type="INQ_ACT_UNLOCK")

    num_past_unlock_inquiries = past_unlock_inquiries.count()

    unlocked_count = (
        past_unlock_inquiries.filter(status="INQ_NEW").count()
        + student.unlocked_units.count()
    )

    # auto reject criteria - the current petition counts toward the unlock count
    auto_reject_too_many_unlocks = (
        inquiry.action_type == "INQ_ACT_UNLOCK" and unlocked_count > 9
    )
    auto_reject_exists_pending = inquiry.action_type in (
        "INQ_ACT_DROP",
        "INQ_ACT_LOCK",
    ) and PSet.objects.filter(
        student=student, unit=inquiry.unit, status__in=("P", "PA", "PR")
    )
    auto_reject_criteria = auto_reject_too_many_unlocks or auto_reject_exists_pending

    if auto_reject_criteria:
        inquiry.status = "INQ_REJ"
        inquiry.was_auto_processed = True
        inquiry.save()
        messages.error(
            request,
            message=(
                "You can't have more than 9 unfinished units unlocked at once."
                if auto_reject_too_many_unlocks
                else "You have a pending submission for this unit"
            ),
        )
        return

    # auto hold criteria
    num_psets = PSet.objects.filter(student=student).count()
    auto_hold_criteria = num_past_unlock_inquiries > (10 + 2.5 * num_psets**1.2)

    if auto_hold_criteria:
        inquiry.status = "INQ_HOLD"
        inquiry.save()
        logger.log(
            SUCCESS_LOG_LEVEL,
            f"Held {student}'s petition to {inquiry.action_type} {inquiry.unit} "
            f"({num_psets} psets and {num_past_unlock_inquiries} unlock petitions).",
            extra={"request": request},
        )
        messages.warning(
            request,
            "You have submitted an abnormally large number of petitions "
            + "so you should contact Evan specially to explain why.",
        )
        return

    unit = inquiry.unit

    # auto accepting criteria for unlocking
    if inquiry.action_type == "INQ_ACT_UNLOCK" and unlocked_count <= 9:
        # when less than 6 past unlock (newbie) or a secret unit (currently uses subject to determine this)
        auto_accept_criteria = (
            num_past_unlock_inquiries <= 6 or unit.group.subject == "K"
        )

        auto_accept_criteria |= (
            Student.objects.filter(user=student.user, curriculum__in=[unit])
            .exclude(pk=student.pk)
            .exists()
        )
    elif inquiry.action_type == "INQ_ACT_DROP":
        # auto dropping locked units
        auto_accept_criteria = not student.unlocked_units.contains(unit)
    else:
        auto_accept_criteria = False

    if auto_accept_criteria:
        inquiry.run_accept()
        inquiry.was_auto_processed = True
        inquiry.save()
        messages.success(request, "Petition automatically processed.")
        return

    messages.success(request, "Petition submitted, wait for it!")


# Inquiry views
@login_required
def inquiry(request: AuthHttpRequest, student_pk: int) -> HttpResponse:
    student = get_student_by_pk(request, student_pk)
    if not request.user.is_staff:
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
    context: dict[str, Any] = {}

    # Create form for submitting new inquiries
    if request.method == "POST":
        form = InquiryForm(request.POST, student=student)
        if form.is_valid():
            inquiry: UnitInquiry = form.save(commit=False)
            handle_inquiry(request, inquiry, student)
            return HttpResponseRedirect(reverse("inquiry", args=(student.pk,)))

    else:
        form = InquiryForm(student=student)
    context["form"] = form

    context["inquiries"] = UnitInquiry.objects.filter(student=student)
    context["student"] = student
    context["curriculum"] = student.generate_curriculum_rows()

    return render(request, "roster/inquiry.html", context)


@login_required
def cancel_inquiry(request: AuthHttpRequest, pk: int) -> HttpResponse:
    inquiry = get_object_or_404(UnitInquiry, pk=pk)
    if inquiry.student.user != request.user and not request.user.is_staff:
        raise PermissionDenied("You are not authorized to cancel this inquiry.")
    if inquiry.status != "INQ_NEW":
        raise PermissionDenied
    inquiry.status = "INQ_CANC"
    inquiry.save()
    messages.success(request, "Inquiry successfully canceled.")
    return HttpResponseRedirect(reverse("inquiry", args=(inquiry.student.pk,)))


@login_required
def register(request: AuthHttpRequest) -> HttpResponse:
    try:
        container = RegistrationContainer.objects.get(semester__active=True)
    except (
        RegistrationContainer.DoesNotExist,
        RegistrationContainer.MultipleObjectsReturned,
    ):
        messages.error(request, "Registration is not set up on the website yet.")
        return HttpResponseRedirect(reverse("index"))
    if not container.accepting_responses:
        messages.error(request, "This semester isn't accepting registration yet.")
        return HttpResponseRedirect(reverse("index"))

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
            try:
                au = ApplyUUID.objects.get(uuid=passcode)
                if au.reg is not None:
                    raise PermissionDenied("This UUID was already used.")
            except (ApplyUUID.DoesNotExist, ValidationError):
                au = None

            if au is None and passcode.lower() != container.passcode.lower():
                messages.error(request, message="Wrong passcode")
            else:
                registration = form.save(commit=False)
                registration.container = container
                registration.user = request.user
                registration.save()
                if au is not None:
                    au.reg = registration
                    au.save()
                request.user.first_name = form.cleaned_data["given_name"].strip()
                request.user.last_name = form.cleaned_data["surname"].strip()
                request.user.email = form.cleaned_data["email_address"]
                request.user.save()
                UserProfile.objects.update_or_create(
                    user=request.user,
                    defaults={k: form.cleaned_data[k] for k in EMAIL_PREFERENCE_FIELDS},
                )
                if au is not None:
                    # Instant acceptance for ApplyUUID registrations
                    build_students(
                        StudentRegistration.objects.filter(pk=registration.pk)
                    )
                    messages.success(
                        request,
                        message="Your registration was accepted! "
                        "You can start working now.",
                    )
                else:
                    # Queue for passcode registrations
                    messages.success(request, message="Submitted! Sit tight.")
                return HttpResponseRedirect(reverse("index"))
    else:
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
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        for k in EMAIL_PREFERENCE_FIELDS:
            initial_data_dict[k] = getattr(profile, k)
        form = DecisionForm(initial=initial_data_dict)
    context = {
        "title": f"{semester} Decision Form",
        "form": form,
        "container": container,
    }
    return render(request, "roster/decision_form.html", context)


@login_required
def update_profile(request: AuthHttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = UserForm(request.POST, instance=request.user)
        old_email = request.user.email
        old_first_name = request.user.first_name
        old_last_name = request.user.last_name
        if form.is_valid():
            user: User = form.save(commit=False)
            if old_email != user.email:
                logger.log(
                    SUCCESS_LOG_LEVEL,
                    f"User {user.get_full_name()} ({user.username}) updated their email "
                    f"to {user.email} (from {old_email})",
                    extra={"request": request},
                )
            if old_first_name != user.first_name or old_last_name != user.last_name:
                logger.log(
                    SUCCESS_LOG_LEVEL,
                    f"User {user.username} ({user.email}) changed their name "
                    f"to {user.first_name} {user.last_name} "
                    f"(previously {old_first_name} {old_last_name}).",
                    extra={"request": request},
                )
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
    assert delta in {1, 2}
    try:
        mystery = student.unlocked_units.get(group__name="Mystery")
    except Unit.DoesNotExist:
        raise PermissionDenied(
            f"You don't have the Mystery unit unlocked!\nYou are currently {student}",
        )

    # Patch the exploit in https://github.com/vEnhance/otis-web/issues/447
    # If there is a pending Mystery submission, just accept it but don't process
    try:
        mystery_pset = PSet.objects.exclude(status="A").get(
            unit=mystery, student=student
        )
    except PSet.DoesNotExist:
        pass
    else:
        mystery_pset.next_unit_to_unlock = None
        mystery_pset.save()

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
        "-forgive_date",
        "debt",
        "student__user__first_name",
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
                invoice.forgive_date,
            ]
        )

    pt = PrettyTable()
    pt.field_names = header_row
    title = f"OTIS Giga-Chart ({where}) generated {timestamp}"
    for row in rows:
        pt.add_row(row)

    format_as = format_as.lower()
    if format_as == "csv":
        filename = f"otis-{where}-{timestamp}.csv"
        return HttpResponse(
            content=pt.get_csv_string(),
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    elif format_as == "html":
        context = {"title": title, "table": pt.get_html_string()}
        return render(request, "roster/gigachart.html", context)
    else:
        raise NotImplementedError(f"Format {format_as} not implemented yet")


class StudentAssistantList(StaffRequiredMixin, ListView[Student]):
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


@staff_required
def link_assistant(request: HttpRequest) -> HttpResponse:
    assistant = get_object_or_404(Assistant, user=request.user)
    # Create form for submitting new inquiries
    if request.method == "POST":
        form = LinkAssistantForm(request.POST)
        if form.is_valid():
            student: Student = form.cleaned_data["student"]
            assert student.assistant is None
            student.assistant = assistant
            student.save()
            messages.success(request, f"You were paired with student {student}.")
            logger.log(
                SUCCESS_LOG_LEVEL,
                f"Assistant {assistant} was linked to {student}",
                extra={"request": request},
            )

    else:
        form = LinkAssistantForm()
    context = {
        "form": form,
        "assistant": assistant,
        "current_students": Student.objects.filter(
            assistant=assistant, semester__active=True
        ),
    }

    return render(request, "roster/link_assistant.html", context)


@admin_required
def email_lookup(request: HttpRequest) -> HttpResponse:
    context = {}
    if request.method == "POST":
        form = EmailLookupForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            student = (
                Student.objects.filter(user__email__iexact=email)
                .order_by("-semester__end_year")
                .first()
            )
            if student is None:
                messages.warning(request, "No matches found")
            else:
                return HttpResponseRedirect(student.get_absolute_url())

    else:
        form = EmailLookupForm()
    context["form"] = form
    return render(request, "roster/email_lookup.html", context)


@admin_required
def discord_lookup(request: HttpRequest) -> HttpResponse:
    context = {}
    if request.method == "POST":
        form = DiscordLookupForm(request.POST)
        if form.is_valid():
            discord_handle = form.cleaned_data["discord_handle"]
            lookup: dict[SocialAccount, str] = {}
            for sa in SocialAccount.objects.filter(
                provider="discord", extra_data__icontains=discord_handle
            ).select_related("user")[:5]:
                student = (
                    Student.objects.filter(user=sa.user)
                    .order_by("-semester__end_year")
                    .first()
                )
                if student is not None:
                    lookup[sa] = student.get_absolute_url()
                else:
                    lookup[sa] = reverse("admin:auth_user_change", args=(sa.user.pk,))
            if len(lookup) == 1:
                _, url = list(lookup.items())[0]
                return HttpResponseRedirect(url)
            context["lookup"] = lookup
        else:
            context["lookup"] = None
    else:
        form = DiscordLookupForm()
        context["lookup"] = None
    context["form"] = form
    return render(request, "roster/discord_lookup.html", context)


class AdList(VerifiedRequiredMixin, ListView[Assistant]):
    model = Assistant
    template_name = "roster/ad_list.html"

    context_object_name = "assistants"

    def get_queryset(self) -> QuerySet[Assistant]:
        return Assistant.objects.filter(ad_enabled=True)

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        try:
            context["current_assistant"] = Assistant.objects.get(user=self.request.user)
        except Assistant.DoesNotExist:
            context["current_assistant"] = None
        return context


class AdUpdate(StaffRequiredMixin, UpdateView[Assistant, BaseModelForm[Assistant]]):
    model = Assistant
    template_name = "roster/ad_form.html"
    context_object_name = "assistant"
    fields = ("ad_enabled", "ad_url", "ad_email", "ad_blurb")

    def get_object(self, *args: Any, **kwargs: Any) -> Assistant:
        del args
        del kwargs
        return get_object_or_404(Assistant, user=self.request.user)

    def form_valid(self, form: BaseModelForm[Assistant]):
        messages.success(self.request, "Updated successfully.")
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse("ad-list")
