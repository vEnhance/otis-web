from typing import Optional

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.db.models.query import QuerySet
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404

from roster.models import Student

from . import models


def get_current_students(
    queryset: Optional[QuerySet[Student]] = None,
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

    student = get_object_or_404(models.Student, pk=student_pk)

    if not isinstance(request.user, User):
        raise PermissionDenied("Authentication is needed, how did you even get here?")

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


def infer_student(request: HttpRequest) -> models.Student:
    return models.Student.objects.filter(user=request.user).order_by(
        "-semester__end_year"
    ).first() or get_object_or_404(models.Student, user=request.user)
