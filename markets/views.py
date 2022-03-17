from typing import Any, Dict

from braces.views import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http.request import HttpRequest
from django.http.response import HttpResponseBase, HttpResponseForbidden, HttpResponseNotFound, HttpResponseRedirect  # NOQA
from django.urls.base import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView
from django.views.generic.list import ListView
from otisweb.utils import AuthHttpRequest

from .models import Guess, Market

# Create your views here.


class SubmitGuess(LoginRequiredMixin, CreateView[Guess, BaseModelForm[Guess]]):
	model = Guess
	context_object_name = "guess"
	fields = (
		'value',
		'public',
	)
	request: AuthHttpRequest

	object: Guess
	market: Market

	def form_valid(self, form: BaseModelForm[Guess]):
		messages.success(self.request, f"You submitted a guess of {form.instance.value}")
		form.instance.user = self.request.user
		form.instance.market = self.market
		form.instance.set_score()
		return super().form_valid(form)

	def get_success_url(self) -> str:
		return reverse_lazy('market-pending', args=(self.object.pk, ))

	def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['market'] = self.market
		return context

	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
		self.market = Market.objects.get(slug=kwargs.pop('slug'))
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
			messages.error(request, f"You already submitted {guess.value} for this market.")
			target_url = reverse_lazy('market-pending', args=(guess.pk, ))
			return HttpResponseRedirect(target_url)

		return super().dispatch(request, *args, **kwargs)


class MarketResults(LoginRequiredMixin, ListView[Guess]):
	model = Guess
	context_object_name = "guesses"
	request: AuthHttpRequest
	market: Market
	template_name = 'markets/market_results.html'

	def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['market'] = self.market
		try:
			guess = Guess.objects.get(market=self.market, user=self.request.user)
			context['guess'] = guess
		except Guess.DoesNotExist:
			pass
		context['done'] = (timezone.now() > self.market.end_date)
		assert context['done'] or self.request.user.is_superuser
		return context

	def get_queryset(self) -> QuerySet[Guess]:
		return Guess.objects.filter(market=self.market).order_by('-value')

	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
		if not isinstance(request.user, User):
			return super().dispatch(request, *args, **kwargs)  # login required mixin
		self.market = Market.objects.get(slug=kwargs.pop('slug'))

		if request.user.is_superuser:
			return super().dispatch(request, *args, **kwargs)
		elif not self.market.has_started:
			return HttpResponseNotFound()
		elif not self.market.has_ended:
			return HttpResponseRedirect(self.market.get_absolute_url())
		else:
			return super().dispatch(request, *args, **kwargs)


@require_POST
@user_passes_test(lambda u: u.is_superuser)
def recompute(request: AuthHttpRequest, slug: str):
	guesses = list(Guess.objects.filter(market__slug=slug))
	for guess in guesses:
		guess.set_score()
	Guess.objects.bulk_update(guesses, fields=('score', ), batch_size=50)
	messages.success(
		request, f"Successfully recomputed all {len(guesses)} scores for this market!"
	)
	return HttpResponseRedirect(reverse_lazy('market-results', args=(slug, )))


class MarketList(LoginRequiredMixin, ListView[Market]):
	model = Market
	context_object_name = "markets"
	extra_context = {'past': False}

	def get_queryset(self) -> QuerySet[Market]:
		return Market.started.order_by('-end_date').filter(semester__active=True)


class MarketListPast(MarketList):
	extra_context = {'past': True}

	def get_queryset(self) -> QuerySet[Market]:
		return Market.started.order_by('-end_date').filter(semester__active=False)


class GuessView(LoginRequiredMixin, DetailView[Guess]):
	model = Guess
	context_object_name = "guess"

	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
		guess = self.get_object()
		market = guess.market
		if market.has_ended:
			return HttpResponseRedirect(reverse_lazy('market-results', args=(market.slug, )))
		if guess.user != request.user and not getattr(request.user, 'is_superuser', False):
			return HttpResponseForbidden("You cannot view this guess.")
		return super().dispatch(request, *args, **kwargs)
