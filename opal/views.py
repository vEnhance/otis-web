import datetime
import logging
from typing import Any

from braces.views import SuperuserRequiredMixin
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.db.models.aggregates import Max
from django.db.models.query import QuerySet
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic.list import ListView
from sql_util.utils import SubqueryCount

from evans_django_tools import SUCCESS_LOG_LEVEL
from otisweb.decorators import admin_required, verified_required
from otisweb.mixins import VerifiedRequiredMixin
from otisweb.utils import AuthHttpRequest
from roster.models import Student
from rpg.models import AchievementUnlock

from .forms import AttemptForm
from .models import OpalAttempt, OpalHunt, OpalPuzzle

logger = logging.getLogger(__name__)


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


class AttemptsList(SuperuserRequiredMixin, ListView[OpalAttempt]):
    model = OpalAttempt
    context_object_name = "attempts"

    def setup(self, request: AuthHttpRequest, *args: Any, **kwargs: Any):
        super().setup(request, *args, **kwargs)
        self.puzzle = get_object_or_404(
            OpalPuzzle, hunt__slug=self.kwargs["hunt"], slug=self.kwargs["slug"]
        )

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context["puzzle"] = self.puzzle
        context["num_total"] = self.get_queryset().count()
        context["num_correct"] = self.get_queryset().filter(is_correct=True).count()
        return context

    def get_queryset(self) -> QuerySet[OpalAttempt]:
        return OpalAttempt.objects.filter(puzzle=self.puzzle).order_by("-created_at")


# this is ugly af and untested but i'm getting dinner with my senpai in an hour
@admin_required
def leaderboard(request: AuthHttpRequest, slug: str) -> HttpResponse:
    hunt = get_object_or_404(OpalHunt, slug=slug)
    context: dict[str, Any] = {}
    max_order = OpalPuzzle.objects.filter(hunt=hunt).aggregate(m=Max("order"))["m"]

    correct_attempts = OpalAttempt.objects.filter(
        is_correct=True, puzzle__hunt=hunt
    ).values(
        "user__pk",
        "user__first_name",
        "user__last_name",
        "puzzle__order",
        "created_at",
        "puzzle__is_metapuzzle",
    )
    user_solve_record: dict[int, list] = {}
    num_solves_dict: dict[int, int] = {}
    realname_dict: dict[int, str] = {}
    most_recent_solve_dict: dict[int, datetime.datetime] = {}
    meta_solved_time: dict[int, datetime.datetime] = {}

    for attempt_dict in correct_attempts:
        user_pk: int = attempt_dict["user__pk"]
        if user_pk not in realname_dict:
            realname_dict[user_pk] = (
                attempt_dict["user__first_name"] + " " + attempt_dict["user__last_name"]
            )
        if user_pk not in user_solve_record:
            user_solve_record[user_pk] = [False] * max_order
        user_solve_record[user_pk][attempt_dict["puzzle__order"] - 1] = True

        if user_pk not in num_solves_dict:
            num_solves_dict[user_pk] = 0
        num_solves_dict[user_pk] += 1

        if user_pk not in most_recent_solve_dict:
            most_recent_solve_dict[user_pk] = attempt_dict["created_at"]
        else:
            most_recent_solve_dict[user_pk] = max(
                most_recent_solve_dict[user_pk], attempt_dict["created_at"]
            )
        if attempt_dict["puzzle__is_metapuzzle"]:
            meta_solved_time[user_pk] = attempt_dict["created_at"]

    context["hunt"] = hunt
    context["puzzle_stats"] = (
        OpalPuzzle.objects.filter(hunt=hunt)
        .annotate(
            num_solves=SubqueryCount("opalattempt", filter=Q(is_correct=True)),
            num_total_attempts=SubqueryCount("opalattempt"),
        )
        .values("num_solves", "num_total_attempts", "title", "slug", "order")
    )

    MAX_TIME_IN_FUTURE = datetime.datetime(
        year=datetime.MAXYEAR,
        month=12,
        day=31,
        tzinfo=datetime.timezone.utc,
    )
    context["rows"] = [
        {
            "name": realname_dict[user_pk],
            "user_pk": user_pk,
            "num_solves": num_solves_dict[user_pk],
            "most_recent_solve": most_recent_solve_dict[user_pk],
            "meta_solved_time": meta_solved_time.get(user_pk, None),
            "emoji_string": "".join(
                "✅" if r else "✖️" for r in user_solve_record[user_pk]
            ),
        }
        for user_pk in sorted(
            user_solve_record.keys(),
            key=lambda user_pk: (
                meta_solved_time.get(user_pk, MAX_TIME_IN_FUTURE),
                -num_solves_dict.get(user_pk, 0),
                most_recent_solve_dict[user_pk],
            ),
        )
    ]
    return render(request, "opal/leaderboard.html", context)


@admin_required
def person_log(request: AuthHttpRequest, slug: str, user_pk: int) -> HttpResponse:
    context: dict[str, Any] = {}
    hunt = get_object_or_404(OpalHunt, slug=slug)
    user = get_object_or_404(User, pk=user_pk)
    context["hunt"] = hunt
    context["attempts"] = OpalAttempt.objects.filter(
        puzzle__hunt=hunt, user=user
    ).order_by("-created_at")
    context["hunter"] = user
    context["student"] = (
        Student.objects.filter(user=user).order_by("-semester__end_year").first()
    )
    return render(request, "opal/person_log.html", context)


@verified_required
def show_puzzle(request: AuthHttpRequest, hunt: str, slug: str) -> HttpResponse:
    puzzle = get_object_or_404(OpalPuzzle, hunt__slug=hunt, slug=slug)
    if not puzzle.can_view(request.user):
        if not request.user.is_superuser:
            raise PermissionDenied("This puzzle cannot be unlocked yet")
        elif request.method != "POST":
            messages.warning(
                request, "Only letting you see this cuz you're an admin..."
            )

    past_attempts = OpalAttempt.objects.filter(puzzle=puzzle, user=request.user)
    is_solved = past_attempts.filter(is_correct=True).exists()
    incorrect_attempts = OpalAttempt.objects.filter(
        puzzle=puzzle, user=request.user, excused=False, is_close=False
    ).order_by("-created_at")
    can_attempt = not is_solved and incorrect_attempts.count() < puzzle.guess_limit

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
                solve_message = f"Correct answer to {puzzle.title}!"
                messages.success(request, solve_message)
                if (achievement := puzzle.achievement) is not None:
                    AchievementUnlock.objects.get_or_create(
                        achievement=achievement, user=request.user
                    )
                    solve_message += f" Earned {achievement.diamonds}♦."
                    logger.log(
                        SUCCESS_LOG_LEVEL,
                        f"{request.user} finished the OPAL puzzle {puzzle.title}!",
                        extra={"request": request},
                    )
                    return HttpResponseRedirect(
                        reverse("opal-finish", args=(puzzle.hunt.slug, puzzle.slug))
                    )
            elif attempt.is_close:
                messages.warning(request, f"Keep going for {puzzle.title}...")
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
    context["show_hints"] = timezone.now() >= puzzle.hunt.hints_released_date
    context["incorrect_attempts"] = incorrect_attempts
    return render(request, "opal/showpuzzle.html", context)


@verified_required
def finish(request: AuthHttpRequest, hunt: str, slug: str) -> HttpResponse:
    puzzle = get_object_or_404(OpalPuzzle, hunt__slug=hunt, slug=slug)
    if puzzle.achievement is None:
        raise PermissionDenied("This page is only for puzzles with diamonds.")
    try:
        attempt = OpalAttempt.objects.get(
            puzzle=puzzle, user=request.user, is_correct=True
        )
    except OpalAttempt.DoesNotExist:
        raise PermissionDenied("You did not complete this puzzle.")
    context: dict[str, Any] = {}
    context["puzzle"] = puzzle
    context["hunt"] = puzzle.hunt
    context["achievement"] = puzzle.achievement
    context["attempt"] = attempt
    return render(request, "opal/finish.html", context)
