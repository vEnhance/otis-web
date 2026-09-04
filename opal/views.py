import datetime
import logging
from collections import defaultdict
from collections.abc import Collection, Iterable
from typing import Any, NamedTuple

import requests
from allauth.socialaccount.models import SocialAccount
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.db.models.aggregates import Count, Max, Min
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
from .models import OpalAttempt, OpalHunt, OpalPuzzle, answerize

logger = logging.getLogger(__name__)


def has_early_access(u: User) -> bool:
    return u.is_superuser or u.groups.filter(name="Testsolver").exists()


# How many guesses each hunt contributes to the all-hunts activity page.
RECENT_ATTEMPTS_PER_HUNT = 20
# How many guesses one page of a single hunt's guess log holds.
HUNT_LOG_PAGE_SIZE = 100
# Newest first, with the pk breaking ties. Guesses landing in the same instant
# would otherwise be ordered arbitrarily, which a page boundary turns into a
# guess repeated on one page and missing from the next.
ATTEMPT_LOG_ORDERING = ("-created_at", "-pk")

# A guess eats one of the puzzle's guess limit unless it was right, close, or
# excused by an admin. `_eligibility` enforces this and the logs read it back,
# so what a row calls "out of guesses" is what the puzzle page acted on.
COUNTS_AGAINST_GUESS_LIMIT = Q(excused=False, is_close=False, is_correct=False)


# How a guesser's standing in a hunt tints their row, on the leaderboard and in
# every guess log: blue for a testsolver, green for someone who has finished,
# yellow for a guess on a puzzle its guesser never did get, and red once they
# also ran out of guesses on it.
TESTSOLVER_ROW_CLASS = "table-primary"
FINISHER_ROW_CLASS = "table-success"
UNSOLVED_ROW_CLASS = "table-warning"
EXHAUSTED_ROW_CLASS = "table-danger"


def stats_window(hunt: OpalHunt) -> Q:
    """Which of a hunt's guesses the statistics counts describe.

    Once the hunt opens the counts are about the live hunt, so the testsolve
    guesses from before it drop out. Until then the testsolve is all there is
    to report on, so everything counts.
    """
    return Q(created_at__gte=hunt.start_date) if hunt.has_started else Q()


def correct_emoji(is_testsolver: bool, is_metapuzzle: bool) -> str:
    """The check mark for a correct guess.

    A testsolver's solve is grayed out, since it happened before the hunt was
    open to everyone, and the metapuzzle that ends the hunt gets a glyph of its
    own so a finish is visible at a glance.
    """
    if is_metapuzzle:
        return "🆗" if is_testsolver else "🈴"
    else:
        return "☑️" if is_testsolver else "✅"


def standing_row_class(
    is_testsolver: bool,
    has_finished: bool,
    puzzle_unsolved: bool = False,
    out_of_guesses: bool = False,
) -> str:
    """The Bootstrap tint for a row belonging to a guesser with this standing.

    `puzzle_unsolved` says this row is a guess on a puzzle its guesser has no
    correct answer for anywhere in the hunt, so the guess led nowhere;
    `out_of_guesses` says they also spent that puzzle's whole guess limit, so
    it led nowhere and there is no way back. Both only mean something for a row
    about one puzzle: the leaderboard's rows span the whole hunt, so it leaves
    the two arguments alone.
    """
    if is_testsolver:
        return TESTSOLVER_ROW_CLASS
    elif has_finished:
        return FINISHER_ROW_CLASS
    elif puzzle_unsolved and out_of_guesses:
        return EXHAUSTED_ROW_CLASS
    elif puzzle_unsolved:
        return UNSOLVED_ROW_CLASS
    else:
        return ""


class _Standing(NamedTuple):
    """Where one guesser stands in a hunt, as far as a log row cares.

    A testsolver is someone who solved something before the hunt opened, the
    same test the leaderboard uses, so the two pages agree on who is who.

    The two puzzle sets are kept whole rather than counted, since a row also
    wants to know whether its own puzzle is in either of them.
    """

    solved_puzzles: frozenset[int]
    exhausted_puzzles: frozenset[int]
    is_testsolver: bool
    has_finished: bool

    @property
    def solve_count(self) -> int:
        return len(self.solved_puzzles)


NO_SOLVES = _Standing(
    solved_puzzles=frozenset(),
    exhausted_puzzles=frozenset(),
    is_testsolver=False,
    has_finished=False,
)


def _standings(hunt: OpalHunt, user_pks: Collection[int]) -> dict[int, _Standing]:
    """Each of those users' standing in `hunt`, in one query for the whole page.

    The query groups every guess on the hunt by guesser and puzzle, so a row
    comes back per puzzle a guesser has touched, saying when they first got it
    right (never, if they did not) and how many of their guesses on it ate the
    guess limit. That is enough for all four facts a standing carries, and it
    stays one round trip however long the page is.

    Users who have not guessed on the hunt are absent; `NO_SOLVES` covers them.
    """
    solved: defaultdict[int, set[int]] = defaultdict(set)
    exhausted: defaultdict[int, set[int]] = defaultdict(set)
    testsolvers: set[int] = set()
    finishers: set[int] = set()
    for d in (
        OpalAttempt.objects.filter(puzzle__hunt=hunt, user__in=user_pks)
        .values("user", "puzzle", "puzzle__is_metapuzzle", "puzzle__guess_limit")
        .annotate(
            first_correct=Min("created_at", filter=Q(is_correct=True)),
            num_counted=Count("pk", filter=COUNTS_AGAINST_GUESS_LIMIT),
        )
    ):
        user_pk, puzzle_pk = d["user"], d["puzzle"]
        if (first_correct := d["first_correct"]) is not None:
            solved[user_pk].add(puzzle_pk)
            if first_correct < hunt.start_date:
                testsolvers.add(user_pk)
            if d["puzzle__is_metapuzzle"]:
                finishers.add(user_pk)
        if d["num_counted"] >= d["puzzle__guess_limit"]:
            exhausted[user_pk].add(puzzle_pk)
    return {
        user_pk: _Standing(
            solved_puzzles=frozenset(solved.get(user_pk, ())),
            exhausted_puzzles=frozenset(exhausted.get(user_pk, ())),
            is_testsolver=user_pk in testsolvers,
            has_finished=user_pk in finishers,
        )
        for user_pk in solved.keys() | exhausted.keys()
    }


def decorate_attempts(
    attempts: Iterable[OpalAttempt], hunt: OpalHunt
) -> list[OpalAttempt]:
    """The attempts as a list, each carrying what the guess-log templates show.

    Every log of guesses on `hunt` -- per puzzle, per user, per hunt, and the
    all-hunt activity page -- renders its rows the same way, out of four
    attributes stapled on here:

    * `solve_count`, the number of puzzles of `hunt` the guesser has solved by
      now, which is what makes a row readable: it says how far along the person
      making the guess is.
    * `emoji` and `text_class`, how the guess itself was judged.
    * `row_class`, the tint for where the guesser stands in the hunt, and for
      whether they ever solved the puzzle this row is a guess on and whether
      they still had guesses left on it.

    The standings take a single query for the whole page, since
    `OpalHunt.num_solves` would be one query per row. Pass a queryset that has
    `select_related("user", "puzzle")` on it, or the rows go back to a query
    apiece; `test_guess_log_query_count` is what notices if one stops.
    """
    rows = list(attempts)
    standings = _standings(hunt, {attempt.user.pk for attempt in rows})
    for attempt in rows:
        standing = standings.get(attempt.user.pk, NO_SOLVES)
        attempt.solve_count = standing.solve_count  # type: ignore[attr-defined]
        attempt.row_class = standing_row_class(  # type: ignore[attr-defined]
            is_testsolver=standing.is_testsolver,
            has_finished=standing.has_finished,
            puzzle_unsolved=attempt.puzzle.pk not in standing.solved_puzzles,
            out_of_guesses=attempt.puzzle.pk in standing.exhausted_puzzles,
        )
        if attempt.is_correct:
            attempt.emoji = correct_emoji(  # type: ignore[attr-defined]
                is_testsolver=standing.is_testsolver,
                is_metapuzzle=attempt.puzzle.is_metapuzzle,
            )
            attempt.text_class = "text-success"  # type: ignore[attr-defined]
        elif attempt.is_close:
            attempt.emoji = "▶️"  # type: ignore[attr-defined]
            attempt.text_class = "text-dark"  # type: ignore[attr-defined]
        else:
            attempt.emoji = "✖️"  # type: ignore[attr-defined]
            attempt.text_class = "text-danger"  # type: ignore[attr-defined]
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
                    "This hunt hasn't started yet; this is an internal view for testsolvers and admins.",
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
        hunt = self.puzzle.hunt
        counted = self.get_queryset().filter(stats_window(hunt))
        context["puzzle"] = self.puzzle
        context["num_total"] = counted.count()
        context["num_correct"] = counted.filter(is_correct=True).count()
        context["attempts"] = decorate_attempts(context["object_list"], hunt)
        return context

    def get_queryset(self) -> QuerySet[OpalAttempt]:
        return (
            OpalAttempt.objects.filter(puzzle=self.puzzle)
            .select_related("user", "puzzle")
            .order_by(*ATTEMPT_LOG_ORDERING)
        )


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
        # The log itself lists every guess ever made on the hunt, so the count
        # up top is its own query rather than `paginator.count`.
        context["num_total"] = (
            self.get_queryset().filter(stats_window(self.hunt)).count()
        )
        # Only the current page gets decorated; the queryset itself is every
        # guess ever made on the hunt.
        context["attempts"] = decorate_attempts(context["object_list"], self.hunt)
        return context


@admin_required
def recent_activity(request: AuthHttpRequest) -> HttpResponse:
    """The last few guesses on every hunt at once, newest hunt first."""
    sections = [
        {
            "hunt": hunt,
            "attempts": decorate_attempts(
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
    counted = stats_window(hunt)
    context["puzzles"] = OpalPuzzle.objects.filter(hunt=hunt).annotate(
        num_solves=SubqueryCount("opalattempt", filter=counted & Q(is_correct=True)),
        num_total_attempts=SubqueryCount("opalattempt", filter=counted),
    )

    meta_orders = set(
        OpalPuzzle.objects.filter(hunt=hunt, is_metapuzzle=True).values_list(
            "order", flat=True
        )
    )

    def get_row(user_pk: int) -> dict[str, Any]:
        is_testsolver = user_early_record[user_pk]
        emoji_string = "".join(
            correct_emoji(
                is_testsolver=is_testsolver, is_metapuzzle=order in meta_orders
            )
            if solved
            else "✖️"
            for order, solved in enumerate(user_solve_record[user_pk], start=1)
        )
        return {
            "name": realname_dict[user_pk],
            "user_pk": user_pk,
            "num_solves": num_solves_dict[user_pk],
            "most_recent_solve": most_recent_solve_dict[user_pk],
            "meta_solved_time": meta_solved_time.get(user_pk, None),
            "emoji_string": emoji_string,
            "has_early_access": is_testsolver,
            "row_class": standing_row_class(
                is_testsolver=is_testsolver,
                has_finished=user_pk in meta_solved_time,
            ),
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
    context["attempts"] = decorate_attempts(
        OpalAttempt.objects.filter(puzzle__hunt=hunt, user=user)
        .select_related("user", "puzzle")
        .order_by(*ATTEMPT_LOG_ORDERING),
        hunt,
    )
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
        COUNTS_AGAINST_GUESS_LIMIT, puzzle=puzzle, user=user
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
                # codespell:ignore-next-line callin
                if answerize(attempt.guess).startswith("CALLIN"):
                    messages.info(
                        request,
                        'In puzzle hunts, "call in X" is an instruction to submit the answer X',
                    )
                else:
                    messages.info(request, f"Keep going for {puzzle.title}...")
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
