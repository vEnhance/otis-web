from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Case, Q, Value, When
from django.db.models.expressions import ExpressionWrapper, F
from django.db.models.fields import DecimalField, IntegerField
from django.db.models.functions import Greatest
from django.db.models.query import QuerySet
from django.http import Http404
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils.timezone import localtime

from roster.models import LATE_PAYMENT_GRACE, UPCOMING_PAYMENT_WINDOW, Student

from . import models


def get_current_students(
    queryset: QuerySet[Student] | None = None,
) -> QuerySet[Student]:
    if queryset is None:
        queryset = models.Student.objects.all()
    return queryset.filter(semester__active=True)


def get_visible_from_queryset(user: User, queryset: QuerySet[models.Student]):
    """From a queryset, filter out the students which the user can see."""
    if user.is_superuser:
        return queryset
    else:
        return queryset.filter(
            Q(user=user) | Q(assistant__user=user) | Q(unlisted_assistants__user=user)
        )


def get_visible_students(user: User, current: bool = True):
    queryset = get_current_students() if current else models.Student.objects.all()
    return get_visible_from_queryset(user, queryset)


def get_student_by_pk(
    request: HttpRequest,
    student_pk: int,
    requires_edit: bool = False,
    payment_exempt: bool = False,
) -> models.Student:
    """Returns an ordered pair containing a Student object and
    a boolean indicating whether editing is allowed (is instructor)."""

    student = get_object_or_404(
        models.Student.objects.select_related("user", "semester"), pk=student_pk
    )

    if not isinstance(request.user, User):
        raise PermissionDenied("Authentication is needed, how did you even get here?")

    # sharing the instance lets student.user reuse the request user's cached profile
    if student.user_id == request.user.pk:
        student.user = request.user

    if not payment_exempt and student.is_delinquent and not request.user.is_staff:
        raise PermissionDenied(
            "Payment needs to be processed before this page can be used"
        )

    is_instructor = can_edit(request, student)
    if requires_edit and not is_instructor:
        raise PermissionDenied("Staff member doesn't teach this student")

    if not can_view(request, student):
        raise PermissionDenied("This student is not viewable to the logged in user")

    return student


def can_view(request: HttpRequest, student: models.Student) -> bool:
    return request.user == student.user or can_edit(request, student)


def can_edit(request: HttpRequest, student: models.Student) -> bool:
    if not request.user.is_authenticated:
        raise PermissionDenied("Need login")
    assert isinstance(request.user, User)
    if request.user.is_superuser:
        return True
    return request.user.is_staff and (
        (student.assistant is not None and student.assistant.user == request.user)
        or (student.unlisted_assistants.filter(user=request.user).exists())
    )


def get_regs_missing_us_state(user: User) -> QuerySet[models.StudentRegistration]:
    """The user's USA registrations which don't have a state recorded yet."""
    return models.StudentRegistration.objects.filter(
        user=user, country="USA", us_state=""
    )


def infer_student(request: HttpRequest) -> models.Student:
    if not isinstance(request.user, User):
        raise Http404("Not logged in, so cannot infer a student.")

    student = (
        models.Student.objects.filter(user=request.user)
        .order_by("-semester__end_year")
        .first()
    )
    if student is None:
        raise Http404("No Student matches the given query.")
    else:
        return student


OVERDUE_PAYMENT_STATUSES = frozenset({2, 3, 6, 7})


def annotate_payment_status(queryset: QuerySet[Student]) -> QuerySet[Student]:
    """Evaluate Student.payment_status in SQL, as `payment_status_code`.

    This duplicates the property of the same name, so that a whole roster can
    be classified in a single query; the two must be edited together.

    Also annotates `invoice_total_cost` and `invoice_total_owed`, the SQL
    counterparts of the Invoice properties.
    """
    now = localtime()
    money = DecimalField(max_digits=8, decimal_places=2)
    total_cost = ExpressionWrapper(
        F("semester__prep_rate") * F("invoice__preps_taught")
        + F("semester__hour_rate") * F("invoice__hours_taught")
        + F("invoice__extras")
        + F("invoice__adjustment"),
        output_field=money,
    )
    queryset = queryset.annotate(
        invoice_total_cost=total_cost,
        invoice_total_owed=ExpressionWrapper(
            total_cost - F("invoice__total_paid") - F("invoice__credits"),
            output_field=money,
        ),
        initial_deadline=Case(
            When(
                semester__one_semester_date__isnull=False,
                semester__full_payment_deadline__isnull=False,
                invoice__created_at__gt=F("semester__one_semester_date"),
                then=F("semester__full_payment_deadline"),
            ),
            default=F("semester__half_payment_deadline"),
        ),
    )
    queryset = queryset.annotate(
        initial_due=Greatest("invoice__created_at", "initial_deadline"),
        full_due=Greatest("invoice__created_at", "semester__full_payment_deadline"),
    )
    behind_on_initial = Q(initial_deadline__isnull=False) & Q(
        invoice_total_cost__lt=F("invoice_total_owed") * Value(2, output_field=money)
    )
    # Greatest() is null-propagating on MySQL and SQLite but not on Postgres,
    # so the deadlines are checked for null explicitly rather than via *_due.
    has_full_deadline = Q(semester__full_payment_deadline__isnull=False)
    return queryset.annotate(
        payment_status_code=Case(
            When(
                Q(semester__show_invoices=False)
                | Q(invoice__isnull=True)
                | Q(invoice_total_owed__lte=0),
                then=0,
            ),
            When(
                behind_on_initial & Q(initial_due__lt=now - LATE_PAYMENT_GRACE), then=3
            ),
            When(behind_on_initial & Q(initial_due__lt=now), then=2),
            When(behind_on_initial, then=1),
            When(has_full_deadline & Q(full_due__lt=now - LATE_PAYMENT_GRACE), then=7),
            When(has_full_deadline & Q(full_due__lt=now), then=6),
            When(
                has_full_deadline & Q(full_due__lt=now + UPCOMING_PAYMENT_WINDOW),
                then=5,
            ),
            default=4,
            output_field=IntegerField(),
        )
    )
