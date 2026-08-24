import datetime
import logging
from collections.abc import Iterable
from typing import Any, NamedTuple

import requests
from allauth.socialaccount.models import SocialAccount
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.db.models.aggregates import Count, Max
from django.db.models.manager import Manager
from django.db.models.query import QuerySet
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic.list import ListView
from django_discordo import SUCCESS_LOG_LEVEL
from sql_util.utils import SubqueryCount

from otisweb.decorators import admin_required, verified_required
from otisweb.mixins import AdminRequiredMixin, VerifiedRequiredMixin
from otisweb.utils import AuthHttpRequest
from roster.models import Student
from rpg.models import AchievementUnlock

from .forms import AttemptForm
from .models import OpalAttempt, OpalHunt, OpalPuzzle

logger = logging.getLogger(__name__)


def has_early_access(u: User) -> bool:
    return u.is_staff or u.is_superuser or u.groups.filter(name="Testsolver").exists()


# How many guesses each hunt contributes to the all-hunts activity page.
RECENT_ATTEMPTS_PER_HUNT = 20
# How many guesses one page of a single hunt's guess log holds.
HUNT_LOG_PAGE_SIZE = 100
# Newest first, with the pk breaking ties. Guesses landing in the same instant
# would otherwise be ordered arbitrarily, which a page boundary turns into a
# guess repeated on one page and missing from the next.
ATTEMPT_LOG_ORDERING = ("-created_at", "-pk")


def _with_solve_counts(
    attempts: Iterable[OpalAttempt], hunt: OpalHunt
) -> list[OpalAttempt]:
    """The attempts as a list, each carrying `solve_count` for its guesser.

    That is the number of puzzles of `hunt` the guesser has solved by now, which
    is what makes a row of the log readable: it says how far along the person
    making the guess is. Counted in a single query for the whole page, since
    `OpalHunt.num_solves` would be one query per row.
    """
    rows = list(attempts)
    solve_counts: dict[int, int] = {
        d["user"]: d["num_solves"]
        for d in OpalAttempt.objects.filter(
            puzzle__hunt=hunt,
            user__in=[attempt.user for attempt in rows],
            is_correct=True,
        )
        .values("user")
        .annotate(num_solves=Count("puzzle", distinct=True))
    }
    for attempt in rows:
        attempt.solve_count = solve_counts.get(attempt.user.pk, 0)  # type: ignore[attr-defined]
    return rows


class HuntList(ListView[OpalHunt]):
    model = OpalHunt
    context_object_name = "hunts"

    def get_queryset(self) -> QuerySet[OpalHunt]:
        return OpalHunt.objects.all().order_by("-start_date")

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context["has_early_access"] = (
            has_early_access(self.request.user)
            if isinstance(self.request.user, User)
            else False
        )
        return context


class PuzzleList(VerifiedRequiredMixin, ListView[OpalPuzzle]):
    hunt: OpalHunt
    model = OpalPuzzle
    context_object_name = "puzzles"

    def setup(self, request: AuthHttpRequest, *args: Any, **kwargs: Any):
        super().setup(request, *args, **kwargs)
        self.hunt = get_object_or_404(OpalHunt, slug=self.kwargs["hunt_slug"])
        if not self.hunt.has_started:
            if has_early_access(request.user):
                messages.warning(
                    request,
                    "This hunt hasn't started yet; this is an internal view for testsolvers and staff.",
                )
            else:
                raise PermissionDenied("This puzzle cannot be unlocked yet")

    def get_queryset(self) -> QuerySet[OpalPuzzle]:
        assert isinstance(self.request.user, User)
        return self.hunt.get_queryset_for_user(self.request.user)

    def get_context_data(self, **kwargs: Any):
        assert isinstance(self.request.user, User)
        context = super().get_context_data(**kwargs)
        context["hunt"] = self.hunt
        context["has_early_access"] = has_early_access(self.request.user)
        return context


class AttemptsList(AdminRequiredMixin, ListView[OpalAttempt]):
    model = OpalAttempt
    context_object_name = "attempts"

    def setup(self, request: AuthHttpRequest, *args: Any, **kwargs: Any):
        super().setup(request, *args, **kwargs)
        self.puzzle = get_object_or_404(
            OpalPuzzle,
            hunt__slug=self.kwargs["hunt_slug"],
            slug=self.kwargs["puzzle_slug"],
        )

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context["puzzle"] = self.puzzle
        context["num_total"] = self.get_queryset().count()
        context["num_correct"] = self.get_queryset().filter(is_correct=True).count()
        return context

    def get_queryset(self) -> QuerySet[OpalAttempt]:
        return OpalAttempt.objects.filter(puzzle=self.puzzle).order_by("-created_at")


class HuntAttemptsList(AdminRequiredMixin, ListView[OpalAttempt]):
    """Every guess on one hunt, newest first, a page at a time."""

    hunt: OpalHunt
    model = OpalAttempt
    context_object_name = "attempts"
    template_name = "opal/hunt_log.html"
    paginate_by = HUNT_LOG_PAGE_SIZE

    def setup(self, request: AuthHttpRequest, *args: Any, **kwargs: Any):
        super().setup(request, *args, **kwargs)
        self.hunt = get_object_or_404(OpalHunt, slug=self.kwargs["hunt_slug"])

    def get_queryset(self) -> QuerySet[OpalAttempt]:
        return (
            OpalAttempt.objects.filter(puzzle__hunt=self.hunt)
            .select_related("user", "puzzle")
            .order_by(*ATTEMPT_LOG_ORDERING)
        )

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context["hunt"] = self.hunt
        # Only the current page gets solve counts; the queryset itself is every
        # guess ever made on the hunt.
        context["attempts"] = _with_solve_counts(context["object_list"], self.hunt)
        return context


@admin_required
def recent_activity(request: AuthHttpRequest) -> HttpResponse:
    """The last few guesses on every hunt at once, newest hunt first."""
    sections = [
        {
            "hunt": hunt,
            "attempts": _with_solve_counts(
                OpalAttempt.objects.filter(puzzle__hunt=hunt)
                .select_related("user", "puzzle")
                .order_by(*ATTEMPT_LOG_ORDERING)[:RECENT_ATTEMPTS_PER_HUNT],
                hunt,
            ),
        }
        for hunt in OpalHunt.objects.order_by("-start_date")
    ]
    return render(request, "opal/recent_activity.html", {"sections": sections})


# this is ugly af and untested but i'm getting dinner with my senpai in an hour
@admin_required
def leaderboard(request: AuthHttpRequest, hunt_slug: str) -> HttpResponse:
    hunt = get_object_or_404(OpalHunt, slug=hunt_slug)
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
    user_early_record: dict[int, bool] = {}
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
        if user_pk not in user_early_record:
            user_early_record[user_pk] = False
        if attempt_dict["created_at"] < hunt.start_date:
            user_early_record[user_pk] = True

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
    context["puzzles"] = OpalPuzzle.objects.filter(hunt=hunt).annotate(
        num_solves=SubqueryCount("opalattempt", filter=Q(is_correct=True)),
        num_total_attempts=SubqueryCount("opalattempt"),
    )

    def get_row(user_pk: int) -> dict[str, Any]:
        correct_emoji = "☑️" if user_early_record[user_pk] else "✅"
        emoji_string = "".join(
            correct_emoji if r else "✖️" for r in user_solve_record[user_pk]
        )
        if user_pk in meta_solved_time:
            if user_early_record[user_pk]:
                emoji_string = emoji_string[:-2] + "🆗"
            else:
                emoji_string = emoji_string[:-1] + "🈴"

        return {
            "name": realname_dict[user_pk],
            "user_pk": user_pk,
            "num_solves": num_solves_dict[user_pk],
            "most_recent_solve": most_recent_solve_dict[user_pk],
            "meta_solved_time": meta_solved_time.get(user_pk, None),
            "emoji_string": emoji_string,
            "has_early_access": user_early_record[user_pk],
        }

    MAX_DATETIME = datetime.datetime.max.replace(tzinfo=datetime.UTC)
    sorted_user_pks = sorted(
        user_solve_record.keys(),
        key=lambda user_pk: (
            meta_solved_time.get(user_pk, MAX_DATETIME),
            -num_solves_dict.get(user_pk, 0),
            most_recent_solve_dict[user_pk],
        ),
    )
    context["rows"] = [get_row(user_pk) for user_pk in sorted_user_pks]
    return render(request, "opal/leaderboard.html", context)


@admin_required
def person_log(request: AuthHttpRequest, hunt_slug: str, user_pk: int) -> HttpResponse:
    context: dict[str, Any] = {}
    hunt = get_object_or_404(OpalHunt, slug=hunt_slug)
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


def _discord_send_congratulations(request: AuthHttpRequest, hunt: OpalHunt):
    if not hunt.discord_webhook_url:
        return
    socials: Manager[SocialAccount] = request.user.socialaccount_set  # type: ignore
    discord = socials.filter(provider__iexact="Discord").first()
    if discord is None:
        return
    discord_id = discord.extra_data["id"]
    message = (
        f":checkered_flag: <@{discord_id}> has finished! "
        "You can @ping them to add them to this thread."
    )
    requests.post(url=hunt.discord_webhook_url, json={"content": message})


class _Eligibility(NamedTuple):
    """Where `user` stands on `puzzle`: solved it, guesses spent, guess left?"""

    is_solved: bool
    incorrect_attempts: QuerySet[OpalAttempt]
    can_attempt: bool


def _eligibility(puzzle: OpalPuzzle, user: User) -> _Eligibility:
    is_solved = OpalAttempt.objects.filter(
        puzzle=puzzle, user=user, is_correct=True
    ).exists()
    incorrect_attempts = OpalAttempt.objects.filter(
        puzzle=puzzle,
        user=user,
        excused=False,
        is_close=False,
        is_correct=False,
    ).order_by("-created_at")
    return _Eligibility(
        is_solved=is_solved,
        incorrect_attempts=incorrect_attempts,
        can_attempt=(not is_solved and incorrect_attempts.count() < puzzle.guess_limit),
    )


@verified_required
def show_puzzle(
    request: AuthHttpRequest, hunt_slug: str, puzzle_slug: str
) -> HttpResponse:
    puzzle = get_object_or_404(OpalPuzzle, hunt__slug=hunt_slug, slug=puzzle_slug)
    if not puzzle.can_view(request.user):
        if not has_early_access(request.user):
            raise PermissionDenied("This puzzle cannot be unlocked yet")
        elif request.method != "POST":
            messages.warning(
                request,
                "Warning: this puzzle isn't unlocked yet. Showing for testsolvers and admins only.",
            )

    eligibility = _eligibility(puzzle, request.user)

    if request.method == "POST":
        if not eligibility.can_attempt:
            raise PermissionDenied("You cannot attempt this puzzle anymore.")
        form = AttemptForm(request.POST)
        if form.is_valid():
            # Hold the puzzle row while the guess budget is rechecked and the
            # attempt is written. Without it, guesses submitted in parallel all
            # read the same remaining count and all get evaluated, so the limit
            # can be overrun.
            #
            # The lock has to be on the puzzle and not on the attempts: the race
            # is over a row that doesn't exist yet, and Django talks to MySQL at
            # READ COMMITTED, where InnoDB takes no gap locks. Locking the
            # existing attempts would not stop the new INSERT.
            #
            # Keep this block short and free of network calls: every other guess
            # on this puzzle waits behind the lock until it commits, which is why
            # the Discord ping below stays outside it.
            with transaction.atomic():
                puzzle = OpalPuzzle.objects.select_for_update().get(pk=puzzle.pk)
                if not _eligibility(puzzle, request.user).can_attempt:
                    raise PermissionDenied("You cannot attempt this puzzle anymore.")
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
                    _discord_send_congratulations(request, puzzle.hunt)
                    return HttpResponseRedirect(
                        reverse("opal-finish", args=(puzzle.hunt.slug, puzzle.slug))
                    )
            elif attempt.is_close:
                messages.warning(request, f"Keep going for {puzzle.title}...")
            else:
                messages.warning(request, f"Sorry, wrong answer to {puzzle.title}.")
            return HttpResponseRedirect(puzzle.get_absolute_url())

    elif eligibility.can_attempt is True:
        form = AttemptForm()
    else:
        form = None

    attempts = OpalAttempt.objects.filter(puzzle=puzzle, user=request.user).order_by(
        "-created_at"
    )

    context: dict[str, Any] = {}
    context["puzzle"] = puzzle
    context["hunt"] = puzzle.hunt
    context["solved"] = eligibility.is_solved
    context["attempts"] = attempts
    context["form"] = form
    context["can_attempt"] = eligibility.can_attempt
    context["show_hints"] = (
        timezone.now() >= puzzle.hunt.hints_released_date
        or has_early_access(request.user)
    )
    context["incorrect_attempts"] = eligibility.incorrect_attempts
    return render(request, "opal/showpuzzle.html", context)


@verified_required
def finish(request: AuthHttpRequest, hunt_slug: str, puzzle_slug: str) -> HttpResponse:
    puzzle = get_object_or_404(OpalPuzzle, hunt__slug=hunt_slug, slug=puzzle_slug)
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
