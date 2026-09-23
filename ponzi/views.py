import datetime
from typing import Any

from braces.views import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models.query import QuerySet
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic.list import ListView

from otisweb.decorators import verified_required
from otisweb.utils import AuthHttpRequest
from roster.models import Student
from rpg.levelsys import get_spade_stats

from .forms import InvestmentForm
from .models import (
    INVESTMENT_COOLDOWN,
    TIER_NAMES,
    TIER_RETURNS,
    PonziInvestment,
    PonziScheme,
)


class PonziSchemeList(LoginRequiredMixin, ListView[PonziScheme]):
    model = PonziScheme
    context_object_name = "schemes"

    def get_queryset(self) -> QuerySet[PonziScheme]:
        schemes = PonziScheme.objects.select_related("semester")
        if getattr(self.request.user, "is_staff", False):
            return schemes
        return schemes.filter(start_date__lte=timezone.now())


def find_player(user: User, scheme: PonziScheme) -> Student | None:
    student = Student.objects.filter(user=user, semester=scheme.semester).first()
    if student is None or not student.enabled:
        return None
    return student


def get_player(user: User, scheme: PonziScheme) -> Student:
    student = find_player(user, scheme)
    if student is None:
        raise PermissionDenied("Only active students of this semester can play.")
    return student


def last_investment_date(
    student: Student, scheme: PonziScheme
) -> datetime.datetime | None:
    latest = (
        PonziInvestment.objects.filter(student=student, scheme=scheme)
        .order_by("-created_at")
        .first()
    )
    return None if latest is None else latest.created_at


@login_required
def scheme_detail(request: AuthHttpRequest, pk: int) -> HttpResponse:
    scheme = get_object_or_404(PonziScheme, pk=pk)
    if not scheme.has_started and not request.user.is_staff:
        raise PermissionDenied("This scheme hasn't started yet.")
    student = find_player(request.user, scheme)

    context: dict[str, Any] = {
        "scheme": scheme,
        "student": student,
        "tier_returns": [
            (TIER_NAMES[tier], rate * 100) for tier, rate in TIER_RETURNS.items()
        ],
    }
    if request.user.is_staff:
        context["pool"] = scheme.pool()
        context["num_investors"] = (
            scheme.investments.values("student").distinct().count()
        )
    if student is not None:
        context["investments"] = PonziInvestment.objects.filter(
            student=student, scheme=scheme
        )
        context["balance"] = get_spade_stats(student)
        last = last_investment_date(student, scheme)
        context["next_investment_at"] = (
            None if last is None else last + INVESTMENT_COOLDOWN
        )
        context["can_invest"] = scheme.is_running and (
            last is None or timezone.now() >= last + INVESTMENT_COOLDOWN
        )
        context["form"] = InvestmentForm()
    return TemplateResponse(request, "ponzi/scheme_detail.html", context)


@verified_required
@require_POST
def invest(request: AuthHttpRequest, pk: int) -> HttpResponse:
    scheme = get_object_or_404(PonziScheme, pk=pk)
    student = get_player(request.user, scheme)
    form = InvestmentForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Investments must be a whole number from 1 to 20.")
        return HttpResponseRedirect(scheme.get_absolute_url())
    amount: int = form.cleaned_data["amount"]

    with transaction.atomic():
        scheme = PonziScheme.objects.select_for_update().get(pk=scheme.pk)
        last = last_investment_date(student, scheme)
        if not scheme.is_running:
            messages.error(request, "This scheme is not accepting investments.")
        elif last is not None and timezone.now() < last + INVESTMENT_COOLDOWN:
            messages.error(request, "You can only invest once per week.")
        elif amount > get_spade_stats(student):
            messages.error(request, "You don't have enough spades for that.")
        else:
            PonziInvestment.objects.create(
                scheme=scheme, student=student, amount=amount
            )
            messages.success(request, "Your investment is growing. Trust the process.")
    return HttpResponseRedirect(scheme.get_absolute_url())


def lock_own_investment(
    request: AuthHttpRequest, pk: int
) -> tuple[PonziScheme, PonziInvestment]:
    """Must be called inside a transaction; locks the scheme row, which
    serializes every change to that scheme's pool."""
    investment = get_object_or_404(PonziInvestment, pk=pk, student__user=request.user)
    scheme = PonziScheme.objects.select_for_update().get(pk=investment.scheme_id)
    investment.refresh_from_db()
    get_player(request.user, scheme)
    return scheme, investment


@verified_required
@require_POST
def upgrade(request: AuthHttpRequest, pk: int) -> HttpResponse:
    with transaction.atomic():
        scheme, investment = lock_own_investment(request, pk)
        if not scheme.is_running:
            messages.error(request, "This scheme is no longer running.")
        elif not investment.can_upgrade:
            messages.error(request, "This investment can't be upgraded right now.")
        else:
            investment.target_tier += 1
            investment.upgraded_at = timezone.now()
            investment.save()
            messages.success(request, "Your investment is growing to the next tier.")
    return HttpResponseRedirect(scheme.get_absolute_url())


@verified_required
@require_POST
def withdraw(request: AuthHttpRequest, pk: int) -> HttpResponse:
    with transaction.atomic():
        scheme, investment = lock_own_investment(request, pk)
        if not scheme.is_running:
            messages.error(request, "This scheme is no longer running.")
        elif not investment.can_withdraw:
            messages.error(request, "This investment can't be withdrawn right now.")
        elif (payout := investment.current_value) > scheme.pool():
            scheme.collapsed_at = timezone.now()
            scheme.collapsed_by = investment.student
            scheme.save()
            messages.error(request, "The pool ran dry. The scheme has collapsed!")
        else:
            investment.payout = payout
            investment.withdrawn_at = timezone.now()
            investment.save()
            messages.success(request, f"You withdrew {payout}♠.")
    return HttpResponseRedirect(scheme.get_absolute_url())
