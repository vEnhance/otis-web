from typing import Any, Dict

from braces.views import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.models import User
from django.forms.models import BaseModelForm
from django.http.request import HttpRequest
from django.http.response import HttpResponseBase, HttpResponseForbidden
from django.urls.base import reverse_lazy
from django.utils import timezone
from django.views.generic.edit import CreateView

from .models import Guess, Market

# Create your views here.


class SubmitGuess(LoginRequiredMixin, CreateView[Guess, BaseModelForm[Guess]]):
	model = Guess
	context_object_name = "guess"
	fields = ('value', )

	market: Market

	def form_valid(self, form: BaseModelForm[Guess]):
		assert isinstance(self.request.user, User)

		messages.success(self.request, f"You submitted a guess of {form.instance.value}")
		form.instance.user = self.request.user
		form.instance.market = self.market
		form.instance.set_score()
		return super().form_valid(form)

	def get_success_url(self) -> str:
		return reverse_lazy('index')

	def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['market'] = self.market
		return context

	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
		self.market = Market.objects.get(slug=kwargs.pop('slug'))
		assert isinstance(request.user, User)

		if not self.market.start_date < timezone.now() < self.market.end_date:
			return HttpResponseForbidden("The market is not currently active")
		if Guess.objects.filter(market=self.market, user=request.user).exists():
			return HttpResponseForbidden("You already submitted a guess")

		return super().dispatch(request, *args, **kwargs)
