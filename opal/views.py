from typing import Any

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models.query import QuerySet
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.views.generic.list import ListView

from otisweb.decorators import verified_required
from otisweb.mixins import VerifiedRequiredMixin
from otisweb.utils import AuthHttpRequest

from .forms import AttemptForm
from .models import OpalAttempt, OpalHunt, OpalPuzzle


class HuntList(ListView[OpalHunt]):
    model = OpalHunt
    context_object_name = "hunts"

    def get_queryset(self) -> QuerySet[OpalHunt]:
        return OpalHunt.objects.all().order_by("-start_date")


class PuzzleList(VerifiedRequiredMixin, ListView[OpalPuzzle]):
    hunt: OpalHunt
    model = OpalPuzzle
    context_object_name = "puzzles"

    def setup(self, request: AuthHttpRequest, *args: Any, **kwargs: Any):
        super().setup(request, *args, **kwargs)
        self.hunt = get_object_or_404(OpalHunt, slug=self.kwargs["slug"])
        if not self.hunt.has_started:
            if request.user.is_superuser:
                messages.warning(request, "This hunt hasn't started yet. Admin view.")
            else:
                raise PermissionDenied("This puzzle cannot be unlocked yet")

    def get_queryset(self) -> QuerySet[OpalPuzzle]:
        assert isinstance(self.request.user, User)
        return self.hunt.get_queryset_for_user(self.request.user)

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context["hunt"] = self.hunt
        return context


@verified_required
def show_puzzle(request: AuthHttpRequest, hunt: str, slug: str) -> HttpResponse:
    puzzle = get_object_or_404(OpalPuzzle, hunt__slug=hunt, slug=slug)
    if not puzzle.can_view(request.user):
        if request.user.is_superuser:
            messages.warning(
                request, "Only letting you see this cuz you're an admin..."
            )
        else:
            raise PermissionDenied("This puzzle cannot be unlocked yet")

    past_attempts = OpalAttempt.objects.filter(puzzle=puzzle, user=request.user)
    is_solved = past_attempts.filter(is_correct=True).exists()
    can_attempt = (
        not is_solved
        and past_attempts.exclude(excused=True).count() < puzzle.guess_limit
    )

    if request.method == "POST":
        if not can_attempt:
            raise PermissionDenied("You cannot attempt this puzzle anymore.")
        form = AttemptForm(request.POST)
        if form.is_valid():
            attempt = OpalAttempt(
                guess=form.cleaned_data["guess"],
                user=request.user,
                puzzle=puzzle,
            )
            attempt.save()
            if attempt.is_correct:
                messages.success(request, f"Correct answer to {puzzle.title}!")
            else:
                messages.warning(request, f"Sorry, wrong answer to {puzzle.title}.")
            return HttpResponseRedirect(puzzle.get_absolute_url())

    elif can_attempt is True:
        form = AttemptForm()
    else:
        form = None

    attempts = OpalAttempt.objects.filter(puzzle=puzzle, user=request.user).order_by(
        "-created_at"
    )

    context: dict[str, Any] = {}
    context["puzzle"] = puzzle
    context["hunt"] = puzzle.hunt
    context["solved"] = is_solved
    context["attempts"] = attempts
    context["form"] = form
    context["can_attempt"] = can_attempt
    return render(request, "opal/showpuzzle.html", context)
