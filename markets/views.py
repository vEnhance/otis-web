import datetime
from typing import Any

from braces.views import LoginRequiredMixin, SuperuserRequiredMixin
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Max, Sum
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http.request import HttpRequest
from django.http.response import (  # NOQA
    HttpResponseBase,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404
from django.urls.base import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView
from django.views.generic.list import ListView

from core.models import Semester
from markets.forms import MarketCreateForm
from otisweb.decorators import admin_required
from otisweb.mixins import VerifiedRequiredMixin
from otisweb.utils import AuthHttpRequest

from .models import Guess, Market

# Create your views here.


class SubmitGuess(VerifiedRequiredMixin, CreateView[Guess, BaseModelForm[Guess]]):
    model = Guess
    context_object_name = "guess"
    fields = (
        "value",
        "public",
    )
    request: AuthHttpRequest
    raise_exception = True
    market: Market

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.instance.market = self.market
        form.instance.user = self.request.user
        return form

    def form_valid(self, form: BaseModelForm[Guess]):
        form.instance.market = self.market
        form.instance.user = self.request.user
        messages.success(
            self.request, f"You submitted a guess of {form.instance.value}"
        )
        form.instance.set_score()
        return super().form_valid(form)

    def get_success_url(self) -> str:
        if self.object is not None:
            return reverse("market-pending", args=(self.object.pk,))
        # fallback: get user's guess for market
        guess = Guess.objects.filter(market=self.market, user=self.request.user).first()
        if guess:
            return reverse("market-pending", args=(guess.pk,))
        return reverse("market-results", args=(self.market.slug,))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["market"] = self.market
        return context

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        self.object = None
        self.market = get_object_or_404(Market, slug=kwargs.pop("slug"))
        if not isinstance(request.user, User):
            return super().dispatch(request, *args, **kwargs)  # login required mixin

        if not self.market.has_started:
            return HttpResponseNotFound()
        elif self.market.has_ended:
            return HttpResponseRedirect(self.market.get_absolute_url())
        try:
            guess = Guess.objects.get(market=self.market, user=request.user)
        except Guess.DoesNotExist:
            pass
        else:
            if request.method == "POST":
                # Allow updating the guess if the market is open
                form = self.get_form()
                form.instance = guess
                form.instance.market = self.market
                form.instance.user = request.user
                if form.is_valid():
                    return self.form_valid(form)
                else:
                    return self.form_invalid(form)
            else:
                self.object = guess
                return super().dispatch(request, *args, **kwargs)

        return super().dispatch(request, *args, **kwargs)


class MarketResults(LoginRequiredMixin, ListView[Guess]):
    model = Guess
    context_object_name = "guesses"
    request: AuthHttpRequest
    market: Market
    template_name = "markets/market_results.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["market"] = self.market
        try:
            guess = Guess.objects.get(market=self.market, user=self.request.user)
            context["guess"] = guess
        except Guess.DoesNotExist:
            pass
        context["done"] = timezone.now() > self.market.end_date
        if not (context["done"] or self.request.user.is_superuser):
            raise PermissionDenied("Can't view results of an unfinished market.")
        if self.market.answer is not None:
            context["best_guess"] = (
                Guess.objects.filter(market=self.market).order_by("-score").first()
            )
        return context

    def get_queryset(self) -> QuerySet[Guess]:
        return Guess.objects.filter(market=self.market).order_by("-value")

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        if not isinstance(request.user, User):
            return super().dispatch(request, *args, **kwargs)  # login required mixin
        self.market = get_object_or_404(Market, slug=kwargs.pop("slug"))

        if not self.market.has_started:
            return HttpResponseNotFound()

        if (
            self.market.has_started
            and not self.market.has_ended
            and not request.user.is_superuser
        ):
            try:
                guess = Guess.objects.get(market=self.market, user=request.user)
                return HttpResponseRedirect(reverse("market-pending", args=(guess.pk,)))
            except Guess.DoesNotExist:
                return HttpResponseRedirect(
                    reverse("market-guess", args=(self.market.slug,))
                )

        return super().dispatch(request, *args, **kwargs)


@require_POST
@admin_required
def recompute(request: AuthHttpRequest, slug: str):
    guesses = Guess.objects.filter(market__slug=slug)
    for guess in guesses:
        guess.set_score()
    Guess.objects.bulk_update(guesses, fields=("score",), batch_size=50)
    messages.success(
        request,
        f"Successfully recomputed all {guesses.count()} scores for this market!",
    )
    return HttpResponseRedirect(reverse("market-results", args=(slug,)))


class MarketList(LoginRequiredMixin, ListView[Market]):
    model = Market
    context_object_name = "markets"
    extra_context = {"past": False}

    def get_queryset(self) -> QuerySet[Market]:
        if getattr(self.request.user, "is_staff", False) is True:
            markets = Market.objects
        else:
            markets = Market.upcoming
        return markets.order_by("-end_date").filter(semester__active=True)


class MarketListPast(MarketList):
    extra_context = {"past": True}

    def get_queryset(self) -> QuerySet[Market]:
        if getattr(self.request.user, "is_staff", False) is True:
            markets = Market.objects
        else:
            markets = Market.started
        return markets.order_by("-end_date").filter(semester__active=False)


class MarketSpades(LoginRequiredMixin, ListView[Guess]):
    model = Guess
    context_object_name = "guesses"
    request: AuthHttpRequest
    template_name = "markets/market_spades.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        guesses = self.get_queryset()
        if guesses.exists():
            context.update(guesses.aggregate(total=Sum("score"), avg=Avg("score")))
        return context

    def get_queryset(self) -> QuerySet[Guess]:
        return (
            Guess.objects.filter(
                user=self.request.user,
                market__end_date__lt=timezone.now(),
            )
            .select_related("market")
            .order_by("-market__end_date")
        )


class GuessView(LoginRequiredMixin, DetailView[Guess]):
    model = Guess
    context_object_name = "guess"

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        guess = self.get_object()
        market = guess.market
        if market.has_ended:
            return HttpResponseRedirect(reverse("market-results", args=(market.slug,)))
        if guess.user != request.user and not getattr(
            request.user, "is_superuser", False
        ):
            return HttpResponseForbidden("You cannot view this guess.")
        return super().dispatch(request, *args, **kwargs)


class MarketCreateView(
    SuperuserRequiredMixin, CreateView[Market, BaseModelForm[Market]]
):
    model = Market
    form_class = MarketCreateForm
    object: Market

    def form_valid(self, form: BaseModelForm[Market]):
        messages.success(self.request, f"Created new market {form.instance.slug}.")

        semester = Semester.objects.get(active=True)
        form.instance.semester = semester
        form.instance.prompt = form.cleaned_data["prompt_plain"]
        form.instance.solution = form.cleaned_data["solution_plain"]

        markets = Market.objects.filter(semester__active=True)
        # fmt: off
        max_start_date: datetime.datetime | None = markets.aggregate(a=Max("start_date"))["a"]
        max_end_date: datetime.datetime | None = markets.aggregate(a=Max("end_date"))["a"]
        # fmt: on

        if max_start_date is None:
            start_date = timezone.now() + datetime.timedelta(days=7)
        else:
            start_date = max(
                timezone.now() + datetime.timedelta(hours=1),
                max_start_date + datetime.timedelta(days=7),
            )
        form.instance.start_date = start_date
        if max_end_date is None:
            end_date = timezone.now() + datetime.timedelta(days=10)
        else:
            end_date = max(
                timezone.now() + datetime.timedelta(days=3),
                max_end_date + datetime.timedelta(days=7),
            )
        form.instance.end_date = end_date

        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse("market-list")
