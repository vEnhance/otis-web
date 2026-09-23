import datetime
from typing import Any, ClassVar

from django.contrib import messages
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

from core.utils import find_profile
from otisweb.decorators import verified_required
from otisweb.mixins import VerifiedRequiredMixin
from otisweb.utils import AuthHttpRequest
from rpg.levelsys import Meter, get_spade_stats

from .forms import InvestmentForm
from .models import (
    INVESTMENT_COOLDOWN,
    MAX_INVESTMENT,
    TIER_NAMES,
    TIER_RETURNS,
    PonziInvestment,
    PonziScheme,
)


class PonziSchemeList(VerifiedRequiredMixin, ListView[PonziScheme]):
    model = PonziScheme
    context_object_name = "schemes"
    extra_context: ClassVar[dict[str, Any]] = {
        "max_bid": MAX_INVESTMENT,
        "tier_returns": [
            (TIER_NAMES[tier], rate * 100) for tier, rate in TIER_RETURNS.items()
        ],
    }

    def get_queryset(self) -> QuerySet[PonziScheme]:
        if getattr(self.request.user, "is_staff", False):
            return PonziScheme.objects.all()
        return PonziScheme.objects.filter(start_date__lte=timezone.now())


def last_investment_date(user: User, scheme: PonziScheme) -> datetime.datetime | None:
    latest = (
        PonziInvestment.objects.filter(user=user, scheme=scheme)
        .order_by("-created_at")
        .first()
    )
    return None if latest is None else latest.created_at


@verified_required
def scheme_detail(request: AuthHttpRequest, pk: int) -> HttpResponse:
    scheme = get_object_or_404(PonziScheme, pk=pk)
    if not scheme.has_started and not request.user.is_staff:
        raise PermissionDenied("This scheme hasn't started yet.")
    profile = find_profile(request.user)
    last = last_investment_date(request.user, scheme)

    context: dict[str, Any] = {
        "scheme": scheme,
        "max_bid": MAX_INVESTMENT,
        "num_investors": scheme.investments.values("user").distinct().count(),
        "investments": PonziInvestment.objects.filter(user=request.user, scheme=scheme),
        "spades_meter": Meter.SpadeMeter(
            round(get_spade_stats(request.user), 2),
            dynamic_progress=profile is not None and profile.dynamic_progress,
        ),
        "next_investment_at": None if last is None else last + INVESTMENT_COOLDOWN,
        "can_invest": scheme.is_running
        and (last is None or timezone.now() >= last + INVESTMENT_COOLDOWN),
        "form": InvestmentForm(),
    }
    if request.user.is_superuser or scheme.has_collapsed:
        context["summary"] = scheme.summary()
        context["all_investments"] = scheme.investments.select_related("user").order_by(
            "created_at"
        )
    return TemplateResponse(request, "ponzi/scheme_detail.html", context)


@verified_required
@require_POST
def invest(request: AuthHttpRequest, pk: int) -> HttpResponse:
    scheme = get_object_or_404(PonziScheme, pk=pk)
    form = InvestmentForm(request.POST)
    if not form.is_valid():
        messages.error(
            request, f"Bids must be a whole number from 1 to {MAX_INVESTMENT}."
        )
        return HttpResponseRedirect(scheme.get_absolute_url())
    amount: int = form.cleaned_data["amount"]

    with transaction.atomic():
        scheme = PonziScheme.objects.select_for_update().get(pk=scheme.pk)
        last = last_investment_date(request.user, scheme)
        if not scheme.is_running:
            messages.error(request, "This scheme is not accepting bids.")
        elif last is not None and timezone.now() < last + INVESTMENT_COOLDOWN:
            messages.error(request, "You can only bid once per day.")
        elif amount > get_spade_stats(request.user):
            messages.error(request, "You don't have enough spades for that.")
        else:
            PonziInvestment.objects.create(
                scheme=scheme, user=request.user, amount=amount
            )
            messages.success(request, "Action recorded. Thanks for playing!")
    return HttpResponseRedirect(scheme.get_absolute_url())


def lock_own_investment(
    request: AuthHttpRequest, pk: int
) -> tuple[PonziScheme, PonziInvestment]:
    """Must be called inside a transaction; locks the scheme row, which
    serializes every change to that scheme's pool."""
    investment = get_object_or_404(PonziInvestment, pk=pk, user=request.user)
    scheme = PonziScheme.objects.select_for_update().get(pk=investment.scheme_id)
    investment.refresh_from_db()
    return scheme, investment


@verified_required
@require_POST
def upgrade(request: AuthHttpRequest, pk: int) -> HttpResponse:
    with transaction.atomic():
        scheme, investment = lock_own_investment(request, pk)
        if not scheme.is_running:
            messages.error(request, "This scheme is no longer running.")
        elif not investment.can_upgrade:
            messages.error(request, "This bid can't be upgraded right now.")
        else:
            investment.target_tier += 1
            investment.upgraded_at = timezone.now()
            investment.save()
            messages.success(request, "Upgrade has started!")
    return HttpResponseRedirect(scheme.get_absolute_url())


@verified_required
@require_POST
def withdraw(request: AuthHttpRequest, pk: int) -> HttpResponse:
    with transaction.atomic():
        scheme, investment = lock_own_investment(request, pk)
        if not scheme.is_running:
            messages.error(request, "This scheme is no longer running.")
        elif not investment.can_withdraw:
            messages.error(request, "This bid can't be withdrawn right now.")
        elif (payout := investment.current_value) > scheme.pool():
            scheme.collapsed_at = timezone.now()
            scheme.collapsed_by = request.user
            scheme.save()
            messages.error(request, "The scheme has collapsed!")
        else:
            investment.payout = payout
            investment.withdrawn_at = timezone.now()
            investment.save()
            messages.success(request, f"You withdrew {payout}♠.")
    return HttpResponseRedirect(scheme.get_absolute_url())
