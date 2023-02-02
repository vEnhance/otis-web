from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http.request import HttpRequest
from django.http.response import HttpResponseBase, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls.base import reverse
from django.utils import timezone
from django.views.generic.edit import CreateView
from django.views.generic.list import ListView

from hanabi.models import HanabiContest, HanabiPlayer, HanabiReplay

import random


class HanabiContestList(ListView[HanabiContest]):
    model = HanabiContest
    context_object_name = "contests"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["player"] = HanabiPlayer.objects.filter(user=self.request.user).first()
        context["active_contests"] = HanabiContest.objects.filter(
            deadline__gt=timezone.now()
        )
        context["table_password"] = random.randrange(100, 1000)
        return context


class HanabiReplayList(ListView[HanabiReplay]):
    model = HanabiReplay
    context_object_name = "replays"
    contest: HanabiContest

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["contest"] = self.contest
        return context

    def get_queryset(self) -> QuerySet[HanabiReplay]:
        return HanabiReplay.objects.filter(contest=self.contest).order_by(
            "-game_score", "turn_count"
        )

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        self.contest = get_object_or_404(HanabiContest, pk=kwargs.pop("pk"))
        if not self.contest.has_ended and not getattr(
            self.request.user, "is_staff", False
        ):
            raise PermissionDenied("Too early to view results of Hanabi contest")
        return super().dispatch(request, *args, **kwargs)


class HanabiPlayerCreateView(
    LoginRequiredMixin, CreateView[HanabiPlayer, BaseModelForm[HanabiPlayer]]
):
    model = HanabiPlayer
    fields = ("hanab_username",)

    def form_valid(self, form: BaseModelForm[HanabiPlayer]):
        assert isinstance(self.request.user, User)
        messages.success(
            self.request, f"You set your username to {form.instance.hanab_username}."
        )
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse("hanabi-contests")

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        if not isinstance(request.user, User):
            return super().dispatch(request, *args, **kwargs)  # login required mixin
        if not request.user.groups.filter(name="Verified").exists():
            raise PermissionDenied

        if HanabiPlayer.objects.filter(user=request.user).exists():
            messages.error(request, "You already registered a hanab.live username.")
            return HttpResponseRedirect(reverse("hanabi-contests"))

        return super().dispatch(request, *args, **kwargs)
