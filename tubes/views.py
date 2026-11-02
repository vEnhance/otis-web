import io
import statistics
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import timedelta
from typing import Any

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.query import QuerySet
from django.http import Http404, HttpRequest, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from otisweb.decorators import admin_required, verified_required
from otisweb.mixins import VerifiedRequiredMixin

from .forms import (
    OIMEAnswerForm,
    OIMEBulkEditFormSet,
    OIMECommentForm,
    OIMEContributorForm,
    OIMEProposalForm,
    OIMEReleaseForm,
    OIMESelectionForm,
)
from .models import (
    OIMEComment,
    OIMEContributor,
    OIMEFight,
    OIMEProposal,
    OIMESelection,
    OIMEYear,
)

SUBJECT_NAMES = dict(OIMEProposal.SUBJECT_CHOICES)

GIVE_UP_RATE_LIMIT = 2  # max give-ups allowed within the window
GIVE_UP_WINDOW_MINUTES = 10
BROWSE_PAGE_SIZE = 20
BROWSE_DIFFICULTIES = [d for d, _ in OIMEProposal.DIFFICULTY_CHOICES]
BROWSE_LOCK_CHOICES = ("locked", "unlocked")
LANDING_RECENT_COUNT = 5


def _get_contributor(request: HttpRequest) -> OIMEContributor | None:
    if not request.user.is_authenticated:  # type: ignore[union-attr]
        return None
    try:
        return request.user.oime_contributor  # type: ignore[union-attr]
    except OIMEContributor.DoesNotExist:
        return None


def _deny_if_draft(
    request: HttpRequest,
    proposal: OIMEProposal,
    contributor: OIMEContributor | None,
) -> None:
    """Raise unless the viewer may see ``proposal``, which may still be a draft.

    A draft is private work in progress: only its author (and staff) may reach it,
    so that it cannot be testsolved before the author marks it ready.

    The exception is a contributor who already started a fight on the problem before
    the author flipped it back to draft. Locking them out would strand a session with
    the clock still running and no way to submit or give up, so they keep access —
    with a warning, since the problem they are looking at may now be in flux.
    """
    if not proposal.is_draft:
        return
    if contributor is not None and proposal.author == contributor:
        return
    if request.user.is_staff:  # type: ignore[union-attr]
        return
    if (
        contributor is not None
        and OIMEFight.objects.filter(
            contributor=contributor, proposal=proposal
        ).exists()
    ):
        messages.warning(
            request,
            f"The author has taken {proposal.label} back to draft, so it may still "
            "change. You keep access because you already started a session on it.",
        )
        return
    raise PermissionDenied("This proposal is still a draft.")


def _deny_if_frozen(
    request: HttpRequest,
    proposal: OIMEProposal,
    contributor: OIMEContributor | None,
) -> None:
    """Raise unless the viewer may see ``proposal``, which may be archived or retired.

    Archiving is staff pulling a problem out of circulation, so an archived problem
    is readable only by staff and by its author; it is also frozen, in that nobody
    starts a session on it, upvotes it or comments on it any more (see
    :func:`_get_solver_context`). A retired problem, one that appeared in a Mock
    AIME that has since been released, is treated the same way.

    As with drafts, a contributor who already started a session keeps read access.
    Nothing is hidden from them that they have not already seen, and locking them
    out would strand an attempt with the clock still running and no way to submit
    or give up.
    """
    if not proposal.is_frozen:
        return
    if contributor is not None and proposal.author == contributor:
        return
    if request.user.is_staff:  # type: ignore[union-attr]
        return
    if (
        contributor is not None
        and OIMEFight.objects.filter(
            contributor=contributor, proposal=proposal
        ).exists()
    ):
        reason = (
            "has been archived by staff"
            if proposal.archived
            else "was released in a mock AIME"
        )
        messages.warning(
            request,
            f"{proposal.label} {reason}. You keep access because "
            "you already started a session on it.",
        )
        return
    if proposal.archived:
        raise PermissionDenied("This proposal has been archived.")
    raise PermissionDenied("This proposal was released in a mock AIME.")


def _deny_if_hidden(
    request: HttpRequest,
    proposal: OIMEProposal,
    contributor: OIMEContributor | None,
) -> None:
    """Raise unless the viewer may see ``proposal`` at all.

    Every per-proposal view starts here, so that a problem withdrawn from the
    listings — as a draft, or frozen by archiving or retirement — cannot be
    reached by URL either.
    """
    _deny_if_draft(request, proposal, contributor)
    _deny_if_frozen(request, proposal, contributor)


def _resolve_active_fight(request: HttpRequest) -> OIMEFight | None:
    """The caller's fight that is still running, if there is one.

    People close the fight page and forget about it, leaving an attempt open while its
    clock keeps ticking. So an attempt found past its time limit is closed out here as
    a time-out and reported via a message, rather than left dangling forever; a fight
    still within its limit is handed back so the caller can be offered a way to resume.

    Only ranked mode creates fights, so there is nothing to find for a casual browser.
    """
    if not request.user.is_authenticated:  # type: ignore[union-attr]
        return None
    contributor = _get_contributor(request)
    if contributor is None:
        return None
    fight = (
        OIMEFight.objects.filter(contributor=contributor, status="OIME_TBD")
        .select_related("proposal")
        .first()
    )
    if fight is None:
        return None
    if fight.time_expired:
        fight.status = "OIME_TLE"
        fight.submitted_at = timezone.now()
        fight.save()
        messages.warning(
            request,
            f"Your timed session on {fight.proposal.label} ran out of time and has "
            "been recorded as a time limit exceeded.",
        )
        return None
    return fight


def _is_casual_for(contributor: OIMEContributor, proposal: OIMEProposal) -> bool:
    """Whether this contributor engages with this problem casually rather than ranked.

    True when the contributor is currently in casual mode, or when the problem predates
    their ``ranked_cutoff`` (set when they last returned to ranked mode) — such problems
    could have been browsed casually, so they remain casual-only for that contributor.
    """
    return contributor.casual_mode or (
        contributor.ranked_cutoff is not None
        and proposal.created_at <= contributor.ranked_cutoff
    )


def _annotate_user_status(
    proposals: Sequence[OIMEProposal], contributor: OIMEContributor
) -> None:
    """Tag each proposal with where ``contributor`` stands on it.

    Every listing — the landing tables, the all-problems tables and the per-subject
    browser — answers the same question in its status column, so they all come
    through here. Each proposal gains ``user_fight`` (their fight on it, if any),
    ``has_upvoted``, and ``user_list_status``, one of:

    ``author``
        They wrote it, so it is theirs to publish or keep as a draft.
    ``completed``
        They have a finished fight on it, in either mode: the verdict is the status.
    ``in_progress``
        Their timed session on it is still running.
    ``revealed``
        They took the escape hatch and read the solution without fighting it.
    ``casual``
        Casual for them (see :func:`_is_casual_for`) and not yet opened, so the
        statement is theirs to read whenever they like.
    ``not_started``
        Ranked and never opened. This is the locked state: the statement has to
        stay hidden, because the point of ranked mode is meeting it under the clock.

    Only the proposals handed in are queried, so a page of twenty costs the same
    three queries however long the full list grows.
    """
    pks = [p.pk for p in proposals]
    fights: dict[int, OIMEFight] = {
        f.proposal_id: f  # type: ignore[attr-defined]
        for f in OIMEFight.objects.filter(contributor=contributor, proposal__in=pks)
    }
    revealed_ids = set(
        contributor.revealed_proposals.filter(pk__in=pks).values_list("pk", flat=True)
    )
    upvoted_ids = set(
        OIMEProposal.objects.filter(pk__in=pks, upvotes=contributor).values_list(
            "pk", flat=True
        )
    )
    for proposal in proposals:
        fight = fights.get(proposal.pk)
        proposal.user_fight = fight  # type: ignore[attr-defined]
        proposal.has_upvoted = proposal.pk in upvoted_ids  # type: ignore[attr-defined]
        if proposal.author_id == contributor.pk:  # type: ignore[attr-defined]
            status = "author"
        elif fight is not None and fight.is_complete:
            status = "completed"
        elif proposal.pk in revealed_ids:
            status = "revealed"
        elif fight is not None:
            # A session that has started keeps them on the ranked path for this
            # problem however the mode has changed underneath it, so this beats
            # the casual check below.
            status = "in_progress"
        elif _is_casual_for(contributor, proposal):
            status = "casual"
        else:
            status = "not_started"
        proposal.user_list_status = status  # type: ignore[attr-defined]
        proposal.locked = status == "not_started"  # type: ignore[attr-defined]
        proposal.spoiled = status not in ("not_started", "casual")  # type: ignore[attr-defined]


def _locked_q(contributor: OIMEContributor) -> Q:
    """Match the problems ``contributor`` has never opened, so still under lock.

    The database twin of the ``not_started`` status from
    :func:`_annotate_user_status`, needed because the per-subject browser filters on
    lockedness before paginating. A locked problem is one they could still start a
    timed session on: not theirs, never fought, never revealed, and not already put
    out of ranked reach by a spell in casual mode. Nothing is locked for a
    contributor who is in casual mode right now.
    """
    if contributor.casual_mode:
        return Q(pk__in=[])
    opened = set(
        OIMEFight.objects.filter(contributor=contributor).values_list(
            "proposal_id", flat=True
        )
    ) | set(contributor.revealed_proposals.values_list("pk", flat=True))
    q = ~Q(author=contributor) & ~Q(pk__in=opened)
    if contributor.ranked_cutoff is not None:
        q &= Q(created_at__gt=contributor.ranked_cutoff)
    return q


def _get_solver_context(
    contributor: OIMEContributor,
    proposal: OIMEProposal,
) -> dict[str, Any]:
    """Compute visibility and access flags for a contributor viewing a proposal.

    There are two ways to engage with a problem:

    - **Ranked** (default): the statement is hidden until a timed fight is started,
      and the answer/solution are revealed only once that fight is complete. Solve
      times are recorded.
    - **Casual** (see :func:`_is_casual_for`): every statement is browsable untimed
      and nothing is recorded, but the answer/solution stay hidden until the
      contributor explicitly reveals them on this problem.

    The proposal's author always sees everything.

    Upvoting is gated on having seen the *statement*, not the solution: a casual
    browser may vote on anything they can read, and a ranked contributor from the
    moment they start a fight rather than only once it is finished. Voting on a
    problem you have never opened is the only thing being prevented.

    An archived or retired problem is frozen on top of all that: staff pulled it
    out of circulation, or it appeared in a released contest, so no one starts a
    session on it or upvotes it any more, however they came to still have read
    access to it.
    """
    is_author = contributor == proposal.author
    casual = _is_casual_for(contributor, proposal)
    frozen = proposal.is_frozen

    if is_author:
        return {
            "is_author": True,
            "casual": casual,
            "fight": None,
            "can_see_solution": True,
            "can_start_fight": False,
            "can_upvote": not frozen,
        }

    fight: OIMEFight | None = None
    try:
        fight = OIMEFight.objects.get(contributor=contributor, proposal=proposal)
        if fight.status == "OIME_TBD" and fight.time_expired:
            fight.status = "OIME_TLE"
            fight.submitted_at = timezone.now()
            fight.save()
    except OIMEFight.DoesNotExist:
        pass

    fight_complete = fight is not None and fight.is_complete
    revealed = contributor.revealed_proposals.filter(pk=proposal.pk).exists()

    # A session that has started is never taken away. Whatever has changed since the
    # clock began — the contributor moving to casual mode, the problem going back to
    # draft — they stay on the ranked path for this problem so they can finish it or
    # give up, instead of being stranded with an attempt they cannot close.
    if fight is not None and not fight_complete:
        casual = False

    if casual:
        can_see_solution = revealed or fight_complete
        return {
            "is_author": False,
            "casual": True,
            "fight": fight,
            "can_see_solution": can_see_solution,
            "can_start_fight": False,
            "can_upvote": not frozen,
        }

    # Ranked. Revealing a problem (escape hatch for someone who already knows it,
    # e.g. a co-author) forfeits the chance to fight it and spoils the solution.
    can_see_solution = fight_complete or revealed
    return {
        "is_author": False,
        "casual": False,
        "fight": fight,
        "can_see_solution": can_see_solution,
        "can_start_fight": fight is None and not revealed and not frozen,
        "can_upvote": (fight is not None or revealed) and not frozen,
    }


def _proposal_stats(proposal: OIMEProposal) -> dict[str, Any]:
    """Aggregate testsolve statistics for a problem (completed fights only)."""
    fights = list(
        OIMEFight.objects.filter(proposal=proposal)
        .exclude(status="OIME_TBD")
        .select_related("contributor")
    )
    return _stats_from_fights(fights)


def _bulk_proposal_stats(
    proposals: Iterable[OIMEProposal],
) -> dict[int, dict[str, Any]]:
    """:func:`_proposal_stats` for many problems in one query, keyed by pk."""
    by_proposal: dict[int, list[OIMEFight]] = defaultdict(list)
    fights = (
        OIMEFight.objects.filter(proposal__in=proposals)
        .exclude(status="OIME_TBD")
        .select_related("contributor")
    )
    for fight in fights:
        by_proposal[fight.proposal_id].append(fight)  # type: ignore[attr-defined]
    return {p.pk: _stats_from_fights(by_proposal[p.pk]) for p in proposals}


def _stats_from_fights(fights: Sequence[OIMEFight]) -> dict[str, Any]:
    total = len(fights)
    correct = [f for f in fights if f.status == "OIME_OK"]
    first_correct = [
        f for f in correct if f.wrong_answers == 0 and f.submitted_at is not None
    ]

    def _elapsed(f: OIMEFight) -> int:
        return int((f.submitted_at - f.started_at).total_seconds())  # type: ignore[operator]

    fastest_clean = min(first_correct, key=_elapsed) if first_correct else None

    median_seconds = None
    median_clean = None
    if first_correct:
        median_seconds = round(statistics.median(_elapsed(f) for f in first_correct))
        median_clean = f"{median_seconds // 60:02d}:{median_seconds % 60:02d}"

    def pct(n: int) -> int:
        return round(100 * n / total) if total else 0

    return {
        "total": total,
        "correct": len(correct),
        "correct_pct": pct(len(correct)),
        "first_correct": len(first_correct),
        "first_correct_pct": pct(len(first_correct)),
        "fastest_clean": fastest_clean,
        "fastest_seconds": _elapsed(fastest_clean) if fastest_clean else None,
        "median_clean": median_clean,
        "median_seconds": median_seconds,
    }


# ---------------------------------------------------------------------------
# OIME: Setup / onboarding
# ---------------------------------------------------------------------------


@verified_required
def oime_setup(request: HttpRequest) -> HttpResponse:
    """Create or update OIMEContributor profile."""
    contributor = _get_contributor(request)
    if request.method == "POST":
        form = OIMEContributorForm(request.POST, instance=contributor)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user  # type: ignore[union-attr]
            obj.save()
            return redirect("oime-proposal-list")
    else:
        initial = {}
        if contributor is None:
            initial["display_name"] = request.user.get_full_name()  # type: ignore[union-attr]
        form = OIMEContributorForm(instance=contributor, initial=initial)
    return render(
        request,
        "tubes/oime_setup.html",
        {
            "form": form,
            "is_edit": contributor is not None,
        },
    )


@verified_required
def go_casual(request: HttpRequest) -> HttpResponse:
    """Confirmation page and action for switching into casual mode."""
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")
    if contributor.casual_mode:
        return redirect("oime-proposal-list")
    has_active_fight = OIMEFight.objects.filter(
        contributor=contributor, status="OIME_TBD"
    ).exists()
    if request.method == "POST":
        if has_active_fight:
            messages.error(
                request,
                "You have an active timed session in progress. Finish or give up first.",
            )
            return redirect("oime-casual")
        contributor.casual_mode = True
        contributor.save()
        messages.success(request, "You are now in casual mode.")
        return redirect("oime-proposal-list")
    return render(
        request,
        "tubes/oime_casual_confirm.html",
        {"form": forms.Form(), "has_active_fight": has_active_fight},
    )


@verified_required
def go_serious(request: HttpRequest) -> HttpResponse:
    """Confirmation page and action for returning to ranked mode from casual mode."""
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")
    if not contributor.casual_mode:
        return redirect("oime-proposal-list")
    if request.method == "POST":
        contributor.casual_mode = False
        contributor.ranked_cutoff = timezone.now()
        contributor.save()
        messages.success(request, "You are back in ranked mode.")
        return redirect("oime-proposal-list")
    return render(
        request,
        "tubes/oime_serious_confirm.html",
        {"form": forms.Form()},
    )


def _parse_difficulty(raw: str | None) -> int | None:
    """The difficulty named by a query parameter, or None for "no filter".

    Anything unrecognized is treated as no filter rather than an error: these
    parameters are set by clicking the browser's own buttons, so a bad value only
    ever comes from a hand-edited URL, and dropping it quietly is friendlier than a
    404 on a page whose whole purpose is browsing.
    """
    try:
        difficulty = int(raw or "")
    except ValueError:
        return None
    return difficulty if difficulty in BROWSE_DIFFICULTIES else None


def _parse_lock(raw: str | None) -> str | None:
    """The lock filter named by a query parameter, or None for "no filter".

    Unrecognized values are dropped quietly, for the same reason as in
    :func:`_parse_difficulty`.
    """
    return raw if raw in BROWSE_LOCK_CHOICES else None


def _browse_params(
    sort_by_votes: bool,
    difficulty: int | None,
    lock: str | None = None,
    page: int = 1,
) -> str:
    """The query string (no leading "?") holding the subject browser's settings.

    The page is left out by default: any change of sort or filter reshuffles the list,
    so whatever page the contributor was on no longer means anything. It is only
    passed when returning someone to the exact page they voted from.
    """
    params: dict[str, str] = {}
    if sort_by_votes:
        params["sort"] = "votes"
    if difficulty is not None:
        params["difficulty"] = str(difficulty)
    if lock is not None:
        params["lock"] = lock
    if page > 1:
        params["page"] = str(page)
    return urlencode(params)


def _upvote_return_url(request: HttpRequest) -> str | None:
    """Where a vote cast from the subject browser should land, or None if not from it.

    Voting from the browser should leave the reader where they were rather than
    bouncing them to the problem page. The target is rebuilt from the posted values
    instead of being echoed back, so a forged form can only ever point at a subject
    page of this browser.
    """
    subject = request.POST.get("back_subject", "")
    if subject not in SUBJECT_NAMES:
        return None
    query = QueryDict(request.POST.get("back_params", ""))
    try:
        page = int(query.get("page", ""))
    except ValueError:
        page = 1
    params = _browse_params(
        query.get("sort") == "votes",
        _parse_difficulty(query.get("difficulty")),
        _parse_lock(query.get("lock")),
        page,
    )
    url = reverse("oime-subject-browse", args=[subject])
    return f"{url}?{params}" if params else url


def _difficulty_options(
    sort_by_votes: bool, difficulty: int | None, lock: str | None
) -> list[dict[str, Any]]:
    """The entries of the difficulty dropdown, "All" first and then 1 through 5.

    Each carries the query string that selects it, so the template only has to render
    links; the other controls' settings are preserved by every one of them.
    """
    return [
        {
            "value": value,
            "label": "All" if value is None else f"🔥 × {value}",
            "params": _browse_params(sort_by_votes, value, lock),
            "selected": value == difficulty,
        }
        for value in [None, *BROWSE_DIFFICULTIES]
    ]


def _lock_options(
    sort_by_votes: bool, difficulty: int | None, lock: str | None
) -> list[dict[str, Any]]:
    """The entries of the padlock dropdown: everything, locked only, unlocked only.

    Only ranked contributors are offered this, since nothing is ever locked in casual
    mode; :func:`subject_browse` leaves it out of the context entirely for them.
    """
    labels = {
        None: "All",
        "locked": "🔒 Locked",
        "unlocked": "👀 Unlocked",
    }
    return [
        {
            "value": value,
            "label": labels[value],
            "params": _browse_params(sort_by_votes, difficulty, value),
            "selected": value == lock,
        }
        for value in [None, *BROWSE_LOCK_CHOICES]
    ]


@verified_required
def subject_browse(request: HttpRequest, subject: str) -> HttpResponse:
    """Every problem in one subject, newest first, in pages of 20.

    Casual browsers get what they always got: the full statement of everything, since
    nothing is timed or recorded for them and picking a problem to try is the whole
    idea. Ranked contributors get the same page with the statements they have not
    opened yet held back behind a lock, so the list is useful for scrolling back
    through what they have already fought without ever spoiling what they have not.
    A locked problem cannot be upvoted either; there is nothing to have an opinion
    about yet, and the button sits where a misclick would be easy.

    Three optional query parameters, all driven by controls on the page itself so that
    they survive pagination: ``sort=votes`` orders by upvote count instead of by
    recency, ``difficulty=N`` keeps only problems of that difficulty, and
    ``lock=locked``/``lock=unlocked`` keeps only the problems on one side of the lock
    (offered to ranked contributors only, since nothing is locked in casual mode).
    """
    if subject not in SUBJECT_NAMES:
        raise Http404("Not an OIME subject.")
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    sort_by_votes = request.GET.get("sort") == "votes"
    difficulty = _parse_difficulty(request.GET.get("difficulty"))
    # Nothing is locked in casual mode, so the filter would only ever be a way to ask
    # for an empty page: drop it rather than offer it.
    lock = None if contributor.casual_mode else _parse_lock(request.GET.get("lock"))

    proposals = (
        OIMEProposal.in_pool()
        .filter(subject=subject)
        .select_related("author")
        .annotate(upvote_count=Count("upvotes", distinct=True))
    )
    if difficulty is not None:
        proposals = proposals.filter(difficulty=difficulty)
    if lock == "locked":
        proposals = proposals.filter(_locked_q(contributor))
    elif lock == "unlocked":
        proposals = proposals.exclude(_locked_q(contributor))
    # Ties on upvote count fall back to recency, so the order is always total and
    # pagination cannot show the same problem twice.
    if sort_by_votes:
        proposals = proposals.order_by("-upvote_count", "-pk")
    else:
        proposals = proposals.order_by("-pk")
    paginator = Paginator(proposals, BROWSE_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Work out where the reader stands on each problem on this page, which is what
    # decides whether its statement is shown at all. Only the current page is
    # inspected, so this stays cheap however long the subject list grows.
    page_proposals = list(page_obj.object_list)
    _annotate_user_status(page_proposals, contributor)
    for proposal in page_proposals:
        # Clicking a card's difficulty badge filters down to that difficulty, or
        # clears the filter when it is the one already being applied.
        proposal.difficulty_params = _browse_params(  # type: ignore[attr-defined]
            sort_by_votes,
            None if proposal.difficulty == difficulty else proposal.difficulty,
            lock,
        )
    page_obj.object_list = page_proposals

    return render(
        request,
        "tubes/subject_browse.html",
        {
            "page_obj": page_obj,
            "contributor": contributor,
            "subject": subject,
            "subject_name": SUBJECT_NAMES[subject],
            "subject_choices": OIMEProposal.SUBJECT_CHOICES,
            "sort_by_votes": sort_by_votes,
            "difficulty": difficulty,
            "lock": lock,
            "browse_params": _browse_params(sort_by_votes, difficulty, lock),
            "sort_toggle_params": _browse_params(not sort_by_votes, difficulty, lock),
            "difficulty_options": _difficulty_options(sort_by_votes, difficulty, lock),
            "lock_options": (
                None
                if contributor.casual_mode
                else _lock_options(sort_by_votes, difficulty, lock)
            ),
            "back_params": _browse_params(
                sort_by_votes, difficulty, lock, page_obj.number
            ),
        },
    )


# ---------------------------------------------------------------------------
# OIME: Proposal list / create / update
# ---------------------------------------------------------------------------


class ContributorRequiredMixin(VerifiedRequiredMixin):
    """Send anonymous users to login and contributor-less users through onboarding."""

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:  # type: ignore[union-attr]
            return redirect("account_login")
        if _get_contributor(request) is None:
            return redirect("oime-setup")
        return super().dispatch(request, *args, **kwargs)  # type: ignore[return-value]


class ProposalListView(ContributorRequiredMixin, ListView[OIMEProposal]):
    model = OIMEProposal
    template_name = "tubes/proposal_list.html"
    context_object_name = "proposals"

    def get_queryset(self) -> QuerySet[OIMEProposal]:
        # Archived and retired proposals are hidden from everyone, authors and
        # staff included; use the Django admin to browse them. Drafts are hidden
        # the same way here, but their authors can find them on the drafts page.
        return (
            OIMEProposal.in_pool()
            .select_related("author")
            .annotate(upvote_count=Count("upvotes", distinct=True))
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        contributor = _get_contributor(self.request)
        context["contributor"] = contributor

        if contributor is None:
            return context

        context["casual"] = contributor.casual_mode
        context["subject_choices"] = OIMEProposal.SUBJECT_CHOICES

        proposals = list(context["proposals"])
        _annotate_user_status(proposals, contributor)

        own: list[OIMEProposal] = []
        browse: list[OIMEProposal] = []
        unsolved: list[OIMEProposal] = []
        completed: list[OIMEProposal] = []
        # One bucket per table on the page. "revealed" and "casual" both mean the
        # problem is readable but no longer fightable, so they share a table.
        buckets = {
            "author": own,
            "completed": completed,
            "revealed": browse,
            "casual": browse,
            "in_progress": unsolved,
            "not_started": unsolved,
        }
        for proposal in proposals:
            buckets[proposal.user_list_status].append(proposal)  # type: ignore[attr-defined]

        context["own_proposals"] = own
        context["browse_proposals"] = browse
        context["unsolved_proposals"] = unsolved
        context["completed_proposals"] = completed

        return context


def _proposals_open(request: HttpRequest) -> bool:
    """Whether this user may publish a problem right now.

    Publishing is accepted only while some year's proposal window is open; drafts
    can be written and edited at any time.
    """
    if request.user.is_staff:  # type: ignore[union-attr]
        return True
    return OIMEYear.accepting().exists()


def _can_edit(
    request: HttpRequest,
    proposal: OIMEProposal,
    contributor: OIMEContributor | None,
) -> bool:
    """Whether this user may edit ``proposal`` through the proposal form.

    Staff always may. Authors may until the problem is selected for a contest,
    after which it is edited in the Overleaf instead.
    """
    if request.user.is_staff:  # type: ignore[union-attr]
        return True
    return (
        contributor is not None
        and proposal.author == contributor
        and not proposal.is_selected
    )


class ProposalCreateView(
    ContributorRequiredMixin, CreateView[OIMEProposal, OIMEProposalForm]
):
    model = OIMEProposal
    form_class = OIMEProposalForm
    template_name = "tubes/proposal_form.html"

    def get_initial(self) -> dict[str, Any]:
        initial = super().get_initial()
        contributor = _get_contributor(self.request)
        if contributor is not None:
            initial["credit"] = contributor.display_name
        if not _proposals_open(self.request):
            initial["is_draft"] = True
        return initial

    def form_valid(self, form: OIMEProposalForm) -> HttpResponse:
        contributor = _get_contributor(self.request)
        if contributor is None:
            return redirect("oime-setup")
        if not form.cleaned_data["is_draft"] and not _proposals_open(self.request):
            form.add_error(
                "is_draft",
                "Proposals are closed right now, so this can only be saved as a draft.",
            )
            return self.form_invalid(form)
        form.instance.author = contributor
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["action"] = "Submit"
        context["submit_name"] = "Write Proposal"
        return context


class ProposalUpdateView(
    VerifiedRequiredMixin, UpdateView[OIMEProposal, OIMEProposalForm]
):
    model = OIMEProposal
    form_class = OIMEProposalForm
    template_name = "tubes/proposal_form.html"

    def get_object(
        self, queryset: QuerySet[OIMEProposal] | None = None
    ) -> OIMEProposal:
        proposal = super().get_object(queryset)
        contributor = _get_contributor(self.request)
        if not _can_edit(self.request, proposal, contributor):
            if contributor is not None and proposal.author == contributor:
                raise PermissionDenied(
                    "This problem should be edited in the Overleaf, not here."
                )
            raise PermissionDenied("You can only edit your own proposals.")
        self.was_draft = proposal.is_draft
        return proposal

    def form_valid(self, form: OIMEProposalForm) -> HttpResponse:
        # Taking a draft public is the real act of submission, so it is held to the
        # proposal window. Going back to draft is held to it too: otherwise an author
        # could pull a published problem out of the pool and be unable to return it.
        is_draft = form.cleaned_data["is_draft"]
        if is_draft != self.was_draft and not _proposals_open(self.request):
            form.add_error(
                "is_draft",
                "Proposals are closed right now, so a published problem must stay "
                "published."
                if is_draft
                else "Proposals are closed right now, so this must stay a draft.",
            )
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["action"] = "Update"
        context["submit_name"] = "Update Proposal"
        return context


# ---------------------------------------------------------------------------
# OIME: Proposal detail and solve views
# ---------------------------------------------------------------------------


@verified_required
def start_fight(request: HttpRequest, pk: int) -> HttpResponse:
    """Pre-fight screen (GET) and the action that begins a timed session (POST).

    A POST creates the fight and redirects into the timed solving view; a GET shows
    the intro screen with the "start" and "I already know it" options.
    """
    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    _deny_if_hidden(request, proposal, contributor)

    ctx = _get_solver_context(contributor, proposal)
    # Only reachable while the user can actually start a fight; otherwise show detail.
    if not ctx["can_start_fight"]:
        return redirect("oime-proposal-detail", pk)

    if request.method == "POST":
        # Hold the contributor row across the check and the create. The unique
        # constraint on the fight is (contributor, proposal), so it does nothing
        # to stop starts on two *different* proposals from both finding no active
        # session and each opening one.
        with transaction.atomic():
            OIMEContributor.objects.select_for_update().get(pk=contributor.pk)
            if OIMEFight.objects.filter(
                contributor=contributor, status="OIME_TBD"
            ).exists():
                messages.error(
                    request, "You already have an active timed session in progress."
                )
                return redirect("oime-proposal-detail", pk)
            OIMEFight.objects.create(contributor=contributor, proposal=proposal)
        return redirect("oime-proposal-fight", pk)

    return render(
        request,
        "tubes/start_fight.html",
        {"proposal": proposal, "contributor": contributor, **ctx},
    )


@verified_required
def proposal_detail(request: HttpRequest, pk: int) -> HttpResponse:
    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    _deny_if_hidden(request, proposal, contributor)

    ctx = _get_solver_context(contributor, proposal)
    fight: OIMEFight | None = ctx["fight"]

    # Ranked contributor with an active fight → send to the timed fight view
    if not ctx["casual"] and fight is not None and not fight.is_complete:
        return redirect("oime-proposal-fight", pk)
    # Hasn't engaged yet → send to the pre-fight start screen
    if ctx["can_start_fight"]:
        return redirect("oime-start-fight", pk)

    comment_form = OIMECommentForm()
    # The discussion on a frozen problem is frozen along with the rest of it.
    can_comment = ctx["can_see_solution"] and not proposal.is_frozen

    if request.method == "POST" and "submit_comment" in request.POST:
        if not can_comment:
            raise PermissionDenied
        comment_form = OIMECommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.author = contributor
            comment.proposal = proposal
            comment.save()
            return redirect("oime-proposal-detail", pk)

    comments = (
        OIMEComment.objects.filter(proposal=proposal).select_related("author")
        if ctx["can_see_solution"]
        else None
    )
    has_upvoted = (
        proposal.upvotes.filter(pk=contributor.pk).exists()
        if ctx["can_upvote"]
        else False
    )
    # Detail is only reached once the user can no longer start a fight, so always
    # show the testsolve stats summary here.
    stats = _proposal_stats(proposal)

    is_eic: bool = request.user.is_superuser  # type: ignore[union-attr]
    is_staff: bool = request.user.is_staff  # type: ignore[union-attr]
    all_selections = list(proposal.selections.select_related("year", "editor"))
    selections = [
        sel
        for sel in all_selections
        if is_staff
        or sel.editor == contributor
        or (ctx["is_author"] and not sel.is_deferred)
    ]
    cards: list[dict[str, Any]] = [
        {
            "year": sel.year,
            "selection": sel,
            "transitions": sel.transitions(is_eic=is_eic)
            if is_eic or sel.editor == contributor
            else [],
            "form": OIMESelectionForm(instance=sel)
            if is_eic and not sel.is_deferred
            else None,
            # Overleaf is shared with editors, not authors. The editor-in-chief
            # gets it in the row below instead, next to the metadata button.
            "overleaf_inline": not is_eic
            and not sel.is_deferred
            and bool(sel.year.overleaf_url)
            and (is_staff or sel.editor == contributor),
        }
        for sel in selections
    ]
    # An unreviewed problem gets the same card for the current year, with no
    # selection behind it; its buttons write the first verdict.
    current_year = OIMEYear.current() if is_eic else None
    can_triage = (
        current_year is not None
        and not proposal.is_draft
        and not proposal.is_frozen
        and not any(sel.year == current_year for sel in all_selections)
    )
    if can_triage:
        cards.insert(
            0,
            {
                "year": current_year,
                "selection": None,
                "transitions": [
                    ("SEL_SHORTLISTED", "✅ Shortlist"),
                    ("SEL_DEFERRED", "⏸️ Defer"),
                ],
                "form": None,
            },
        )

    return render(
        request,
        "tubes/proposal_detail.html",
        {
            "proposal": proposal,
            "contributor": contributor,
            "comment_form": comment_form,
            "comments": comments,
            "can_comment": can_comment,
            "has_upvoted": has_upvoted,
            "stats": stats,
            "frozen": proposal.is_frozen,
            "can_edit": _can_edit(request, proposal, contributor),
            "selection_cards": cards,
            "can_triage": can_triage,
            "status_choices": OIMESelection.STATUS_CHOICES,
            **ctx,
        },
    )


@verified_required
def proposal_solution_tex(request: HttpRequest, pk: int) -> HttpResponse:
    """Download a problem's answer and solution as a LaTeX file.

    The on-page preview is typeset by MathJax, which understands only a fraction of
    LaTeX, so the source is what a contributor actually wants once a solution uses
    anything beyond basic math mode. Gated exactly like the solution itself: the
    answer is in the file, so anyone who cannot see the solution on the detail page
    must not be able to fetch it here either.
    """
    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    _deny_if_hidden(request, proposal, contributor)

    ctx = _get_solver_context(contributor, proposal)
    if not ctx["can_see_solution"]:
        raise PermissionDenied("You cannot see the solution to this problem yet.")

    written_on = f"{timezone.localtime(proposal.created_at):%Y-%m-%d}"
    content = "\n".join(
        (
            r"\documentclass[11pt]{article}",
            r"\usepackage{amsmath,amsthm,amssymb}",
            r"\begin{document}",
            f"\\title{{{proposal.label}: {proposal.title}}}",
            f"\\author{{{proposal.credit_display}}}",
            f"\\date{{{written_on}}}",
            r"\maketitle",
            "",
            r"\section*{Problem}",
            proposal.statement,
            "",
            f"\\section*{{Answer}}\n{proposal.answer}",
            "",
            r"\section*{Solution}",
            proposal.solution,
            "",
            r"\end{document}",
        )
    )
    filename = f"oime-{proposal.label}.tex"
    return HttpResponse(
        content=content,
        content_type="application/x-tex; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@verified_required
def proposal_fight(request: HttpRequest, pk: int) -> HttpResponse:
    """Timed solving screen for a ranked contributor with an active attempt."""
    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    _deny_if_hidden(request, proposal, contributor)

    ctx = _get_solver_context(contributor, proposal)
    fight: OIMEFight | None = ctx["fight"]

    # Only valid while there is an active, in-progress fight (ranked mode only)
    if ctx["casual"] or fight is None or fight.is_complete:
        return redirect("oime-proposal-detail", pk)

    response = render(
        request,
        "tubes/proposal_fight.html",
        {
            "proposal": proposal,
            "contributor": contributor,
            "fight": fight,
            "remaining_seconds": fight.remaining_seconds,
            "answer_form": OIMEAnswerForm(),
        },
    )
    # Never let this page come back from the browser cache. Otherwise, after giving
    # up and reading the solution, hitting "back" restores this page with a live
    # countdown, which looks like the attempt is still open when it is long over.
    response["Cache-Control"] = "no-store, max-age=0"
    return response


@verified_required
def submit_answer(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("oime-proposal-detail", pk)

    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    # Hold the fight row for the whole adjudication. Answers submitted in
    # parallel would otherwise all read the same wrong_answers and all judge
    # against the same not-yet-terminal status, so the increments clobber each
    # other and more than ANSWER_LIMIT answers get graded.
    with transaction.atomic():
        attempt = get_object_or_404(
            OIMEFight.objects.select_for_update(),
            contributor=contributor,
            proposal=proposal,
        )

        if attempt.status != "OIME_TBD":
            return redirect("oime-proposal-detail", pk)

        if attempt.time_expired:
            attempt.status = "OIME_TLE"
            attempt.submitted_at = timezone.now()
            attempt.save()
            messages.warning(
                request, "The time limit for your timed session has expired."
            )
            return redirect("oime-proposal-detail", pk)

        form = OIMEAnswerForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please enter a valid integer (0-999).")
            return redirect("oime-proposal-fight", pk)

        submitted = form.cleaned_data["answer"]
        if submitted == proposal.answer:
            attempt.status = "OIME_OK"
            attempt.submitted_at = timezone.now()
            attempt.save()
            messages.success(request, f"Correct! You took {attempt.time_display}.")
        else:
            attempt.wrong_answers += 1
            if attempt.wrong_answers >= OIMEFight.ANSWER_LIMIT:
                attempt.status = "OIME_ALE"
                attempt.submitted_at = timezone.now()
                attempt.save()
                messages.error(
                    request,
                    f"Incorrect. You have used all {OIMEFight.ANSWER_LIMIT} attempts.",
                )
            else:
                attempt.save()
                remaining = OIMEFight.ANSWER_LIMIT - attempt.wrong_answers
                messages.error(
                    request,
                    f"Incorrect. {remaining} attempt{'' if remaining == 1 else 's'} remaining.",
                )

    return redirect("oime-proposal-fight", pk)


@verified_required
def give_up(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("oime-proposal-detail", pk)

    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    # The contributor lock is what makes the give-up rate limit hold: it counts
    # rows across proposals, so give-ups on two problems at once would otherwise
    # both read the same count. This is the only view here that takes both locks,
    # and no other takes the fight before the contributor, so the order can't
    # cycle.
    with transaction.atomic():
        OIMEContributor.objects.select_for_update().get(pk=contributor.pk)
        attempt = get_object_or_404(
            OIMEFight.objects.select_for_update(),
            contributor=contributor,
            proposal=proposal,
        )

        # A session whose clock already ran out is a time-out, not a give-up: record
        # it as such so it neither burns a give-up nor logs a bogus multi-hour time.
        if attempt.status == "OIME_TBD" and attempt.time_expired:
            attempt.status = "OIME_TLE"
            attempt.submitted_at = timezone.now()
            attempt.save()
            messages.warning(
                request, "The time limit for your timed session has expired."
            )
            return redirect("oime-proposal-detail", pk)

        if attempt.status == "OIME_TBD":
            window_start = timezone.now() - timedelta(minutes=GIVE_UP_WINDOW_MINUTES)
            recent_give_ups = OIMEFight.objects.filter(
                contributor=contributor,
                status="OIME_FAIL",
                submitted_at__gte=window_start,
            ).count()
            if recent_give_ups >= GIVE_UP_RATE_LIMIT:
                messages.error(
                    request,
                    f"You have given up {GIVE_UP_RATE_LIMIT} times in the last "
                    f"{GIVE_UP_WINDOW_MINUTES} minutes. Please wait before giving up again.",
                )
                return redirect("oime-proposal-fight", pk)
            attempt.status = "OIME_FAIL"
            attempt.submitted_at = timezone.now()
            attempt.save()
            messages.info(
                request, "You gave up on this problem. You can now view the solution."
            )

    return redirect("oime-proposal-detail", pk)


@verified_required
def reveal_solution(request: HttpRequest, pk: int) -> HttpResponse:
    """Reveal the answer and solution for a single problem.

    Used both by casual browsing and as a ranked-mode escape hatch for someone who
    already knows a problem (e.g. a co-author). Revealing forfeits the chance to fight
    it, so it is refused while a timed fight is in progress.
    """
    if request.method != "POST":
        return redirect("oime-proposal-detail", pk)

    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    _deny_if_hidden(request, proposal, contributor)

    # Same contributor lock as start_fight, so that revealing and starting a
    # fight can't interleave and leave the problem both revealed and being fought.
    with transaction.atomic():
        OIMEContributor.objects.select_for_update().get(pk=contributor.pk)
        active_fight = OIMEFight.objects.filter(
            contributor=contributor, proposal=proposal, status="OIME_TBD"
        ).exists()
        if active_fight:
            raise PermissionDenied

        contributor.revealed_proposals.add(proposal)
    return redirect("oime-proposal-detail", pk)


@verified_required
def upvote_proposal(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("oime-proposal-detail", pk)

    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    _deny_if_hidden(request, proposal, contributor)

    ctx = _get_solver_context(contributor, proposal)
    if not ctx["can_upvote"]:
        raise PermissionDenied

    if proposal.upvotes.filter(pk=contributor.pk).exists():
        proposal.upvotes.remove(contributor)
    else:
        proposal.upvotes.add(contributor)

    return redirect(
        _upvote_return_url(request) or reverse("oime-proposal-detail", args=[pk])
    )


@verified_required
def toggle_archive(request: HttpRequest, pk: int) -> HttpResponse:
    """Flip a problem's archived state. Archiving is a staff-only moderation action."""
    if request.method != "POST":
        return redirect("oime-proposal-detail", pk)
    proposal = get_object_or_404(OIMEProposal, pk=pk)
    if not request.user.is_superuser:  # type: ignore[union-attr]
        raise PermissionDenied
    proposal.archived = not proposal.archived
    proposal.save(update_fields=["archived"])
    return redirect("oime-proposal-detail", pk)


@verified_required
def proposal_results(request: HttpRequest, pk: int) -> HttpResponse:
    """Leaderboard of every fight on a problem, for contributors who can no longer fight it."""
    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    _deny_if_hidden(request, proposal, contributor)

    # The leaderboard is for anyone who can no longer start a fight on the problem
    # (casual browsers, those who have fought or revealed it, and the author).
    ctx = _get_solver_context(contributor, proposal)
    if ctx["can_start_fight"]:
        return redirect("oime-proposal-detail", pk)

    fights = list(
        OIMEFight.objects.filter(proposal=proposal)
        .exclude(status="OIME_TBD")
        .select_related("contributor")
    )
    # Rank: solved first, then fewest wrong answers, then fastest solve time.
    fights.sort(
        key=lambda f: (
            f.status != "OIME_OK",
            f.wrong_answers,
            (
                int((f.submitted_at - f.started_at).total_seconds())
                if f.status == "OIME_OK" and f.submitted_at is not None
                else 1_000_000
            ),
        )
    )

    return render(
        request,
        "tubes/proposal_results.html",
        {
            "proposal": proposal,
            "contributor": contributor,
            "fights": fights,
            # The stats table leads with this viewer's own verdict on the problem.
            "fight": ctx["fight"],
            "stats": _proposal_stats(proposal),
        },
    )


@verified_required
def edit_comment(request: HttpRequest, pk: int) -> HttpResponse:
    comment = get_object_or_404(OIMEComment, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")
    if comment.author != contributor and not request.user.is_staff:  # type: ignore[union-attr]
        raise PermissionDenied
    # A frozen problem's discussion is frozen, so its comments are read-only too.
    if comment.proposal.is_frozen:
        raise PermissionDenied("This proposal has been closed.")

    if request.method == "POST":
        form = OIMECommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            return redirect("oime-proposal-detail", pk=comment.proposal_id)  # type: ignore[attr-defined]
    else:
        form = OIMECommentForm(instance=comment)

    return render(
        request, "tubes/comment_edit.html", {"form": form, "comment": comment}
    )


class LandingView(VerifiedRequiredMixin, TemplateView):
    """The front door: what is new, what you have written, and then the instructions.

    The instructions stop being worth reading after the first visit, so the useful
    things go above them: the newest handful of problems, a way into each subject,
    and the state of your own proposals and drafts.

    None of it means anything without a contributor profile, so someone who has not
    onboarded yet gets the instructions and a way to make one.
    """

    template_name = "tubes/landing.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        # The sidebar sends people here, so this is where someone who abandoned a
        # fight page most likely turns up: surface the open session (or retire it).
        context["active_fight"] = _resolve_active_fight(self.request)
        context["subject_choices"] = OIMEProposal.SUBJECT_CHOICES

        contributor = _get_contributor(self.request)
        context["contributor"] = contributor
        context["accepting_year"] = (
            OIMEYear.accepting().order_by("proposals_close_at").first()
        )
        if contributor is None:
            return context

        # The contest section: the editor-in-chief gets every year, each linking
        # to its desk; everyone else gets problems they are editing or wrote.
        if self.request.user.is_superuser:  # type: ignore[union-attr]
            # Meta.ordering is dropped on aggregate queries, so order explicitly.
            context["years"] = list(
                OIMEYear.objects.annotate(
                    chosen_count=Count(
                        "selections", filter=~Q(selections__status="SEL_DEFERRED")
                    )
                ).order_by("-proposals_open_at")
            )
        elif (year := OIMEYear.current()) is not None:
            mine = list(
                _chosen(year)
                .filter(Q(editor=contributor) | Q(proposal__author=contributor))
                .select_related("editor")
            )
            if mine:
                context["current_year"] = year
                context["my_selections"] = mine
                # Overleaf is shared with editors, not authors.
                context["show_overleaf"] = bool(year.overleaf_url) and (
                    self.request.user.is_staff  # type: ignore[union-attr]
                    or any(sel.editor == contributor for sel in mine)
                )

        recent = list(
            OIMEProposal.in_pool()
            .select_related("author")
            .annotate(upvote_count=Count("upvotes", distinct=True))
            .order_by("-created_at")[:LANDING_RECENT_COUNT]
        )
        # Drafts belong here alongside the published ones: this is the one page that
        # shows an author everything they have written, whatever state it is in.
        own = list(
            OIMEProposal.objects.filter(author=contributor, archived=False)
            .select_related("author")
            .annotate(upvote_count=Count("upvotes", distinct=True))
            .order_by("-created_at")
        )
        _annotate_user_status(recent, contributor)
        _annotate_user_status(own, contributor)
        context["recent_proposals"] = recent
        context["own_proposals"] = own
        return context


# ---------------------------------------------------------------------------
# OIME: Years (editor-in-chief pages)
# ---------------------------------------------------------------------------


def _attach_stats(proposals: Sequence[OIMEProposal]) -> None:
    """Hang testsolve stats and the upvote count on each proposal, in two queries."""
    stats = _bulk_proposal_stats(proposals)
    upvotes = dict(
        OIMEProposal.objects.filter(pk__in=[p.pk for p in proposals])
        .annotate(n=Count("upvotes", distinct=True))
        .values_list("pk", "n")
    )
    for proposal in proposals:
        proposal.stats = stats[proposal.pk]  # type: ignore[attr-defined]
        proposal.upvote_count = upvotes.get(proposal.pk, 0)  # type: ignore[attr-defined]


def _unreviewed(year: OIMEYear) -> QuerySet[OIMEProposal]:
    """Problems in the pool with no verdict for this year, most upvoted first."""
    return (
        OIMEProposal.in_pool()
        .exclude(selections__year=year)
        .annotate(n_upvotes=Count("upvotes", distinct=True))
        .order_by("-n_upvotes", "-pk")
    )


def _year_desk(year: OIMEYear) -> dict[str, Any]:
    """The editor-in-chief's view of one year."""
    selections = list(
        year.selections.select_related("proposal", "proposal__author", "editor")
    )
    chosen = [sel for sel in selections if not sel.is_deferred]
    deferred = [sel for sel in selections if sel.is_deferred]
    pool = list(_unreviewed(year).select_related("author"))
    # Only the pool and deferred tables show stats; the chosen tables do not.
    _attach_stats([sel.proposal for sel in deferred] + pool)
    return {
        "year": year,
        "chosen_eic": [sel for sel in chosen if sel.blocked_on == "EIC"],
        "chosen_others": [sel for sel in chosen if sel.blocked_on != "EIC"],
        "deferred_proposals": [sel.proposal for sel in deferred],
        "pool": pool,
    }


@admin_required
def year_detail(request: HttpRequest, pk: int) -> HttpResponse:
    year = get_object_or_404(OIMEYear, pk=pk)
    return render(request, "tubes/year_detail.html", {"desk": _year_desk(year)})


@admin_required
def year_triage(request: HttpRequest, pk: int) -> HttpResponse:
    """One verdict on one problem for one year, from the buttons on its page.

    ``change_status`` (shortlisted or deferred) writes the selection row (creating it if this is
    the first verdict on the problem this year). ``archive`` sets the global flag
    on the proposal instead, since an archived problem is out for every year.
    Either way the editor-in-chief moves on to the next unreviewed problem, or
    back to the year once there are none left.
    """
    year = get_object_or_404(OIMEYear, pk=pk)
    if request.method != "POST":
        return redirect(year)
    proposal = get_object_or_404(OIMEProposal, pk=request.POST.get("proposal"))
    status = request.POST.get("change_status")
    if status in ("SEL_SHORTLISTED", "SEL_DEFERRED"):
        OIMESelection.objects.update_or_create(
            year=year, proposal=proposal, defaults={"status": status}
        )
    elif "archive" in request.POST:
        proposal.archived = True
        proposal.save(update_fields=["archived"])
    else:
        raise Http404("Unknown triage action.")
    next_proposal = _unreviewed(year).first()
    if next_proposal is None:
        messages.success(request, "Every problem has been reviewed.")
        return redirect(year)
    return redirect(next_proposal)


@verified_required
def selection_action(request: HttpRequest, pk: int) -> HttpResponse:
    """The controls on a selection card, all POSTed from the problem's page.

    ``change_status`` moves the problem along the pipeline. The editor-in-chief
    may move it anywhere; the assigned editor only along the transitions marked
    as theirs, which in practice means handing a finished solution back for
    review. ``save`` writes the editor, notes and description, editor-in-chief
    only.
    """
    selection = get_object_or_404(
        OIMESelection.objects.select_related("proposal", "editor"), pk=pk
    )
    contributor = _get_contributor(request)
    is_eic: bool = request.user.is_superuser  # type: ignore[union-attr]
    is_editor = contributor is not None and selection.editor == contributor
    if not (is_eic or is_editor):
        raise PermissionDenied("You are not the editor of this problem.")
    if request.method != "POST":
        return redirect(selection.proposal)

    if "change_status" in request.POST:
        target = request.POST["change_status"]
        if is_eic:
            allowed = {value for value, _ in OIMESelection.STATUS_CHOICES}
        else:
            allowed = {t for t, _ in selection.transitions(is_eic=False)}
        if target not in allowed:
            raise PermissionDenied("That status change is not available to you.")
        selection.status = target
        selection.save(update_fields=["status", "updated_at"])
        label = selection.get_status_display()  # type: ignore[attr-defined]
        messages.success(request, f"{selection.proposal.label} is now {label}.")
    elif "save" in request.POST:
        if not is_eic:
            raise PermissionDenied("Only the editor-in-chief can assign editors.")
        form = OIMESelectionForm(request.POST, instance=selection)
        if form.is_valid():
            form.save()
        else:
            messages.error(request, "Could not save the selection.")
    return redirect(selection.proposal)


@admin_required
def year_release(request: HttpRequest, pk: int) -> HttpResponse:
    """Interstitial for setting (or clearing) the moment the contest goes public.

    Lists exactly the problems that will be retired, so a problem that was cut but
    never marked deferred is caught here rather than discovered when a testsolver
    complains, and warns about anything not yet Done.
    """
    year = get_object_or_404(OIMEYear, pk=pk)
    chosen = list(_chosen(year))
    if request.method == "POST":
        if "clear" in request.POST:
            year.release_at = None
            year.save(update_fields=["release_at"])
            messages.success(request, "Release cleared.")
            return redirect(year)
        form = OIMEReleaseForm(request.POST)
        if form.is_valid():
            year.release_at = form.cleaned_data["release_at"]
            year.save(update_fields=["release_at"])
            messages.success(request, f"Release set for {year}.")
            return redirect(year)
    else:
        initial = timezone.localtime(year.release_at or timezone.now())
        form = OIMEReleaseForm(initial={"release_at": initial})
    return render(
        request,
        "tubes/year_release.html",
        {
            "year": year,
            "form": form,
            "chosen": chosen,
            "not_done": [sel for sel in chosen if sel.status != "SEL_DONE"],
        },
    )


# The export below writes calls to macros defined in oime-tables.tex in the Mock
# AIME repository (\shortdesc, \oimetestsolving, \oimesolves, \oimescore) and
# lays files out where that file reads them (problems/, originals/, data/).
# Renaming a macro or changing its arguments there needs the matching change
# here, and the other way round.
_LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _latex_text(s: str) -> str:
    """Escape a plain-text field (title, name) for use in LaTeX text mode."""
    return "".join(_LATEX_SPECIALS.get(c, c) for c in s)


def _indent(text: str) -> str:
    return "\n".join(
        ("  " + line) if line.strip() else "" for line in text.strip().splitlines()
    )


def _chosen(year: OIMEYear) -> QuerySet[OIMESelection]:
    return year.selections.filter(OIMESelection.CHOSEN).select_related(
        "proposal", "proposal__author"
    )


def _description(sel: OIMESelection) -> str:
    """The EIC's LaTeX description, or else the escaped title."""
    return sel.description or _latex_text(sel.proposal.title)


def _problem_tex(request: HttpRequest, sel: OIMESelection) -> str:
    r"""One ``problems/<label>.tex`` in the house format of the Mock AIME repository.

    ``\shortdesc`` comes before the statement because ``\answer`` and
    ``\credits`` end the file early on some passes.
    """
    proposal = sel.proposal
    url = request.build_absolute_uri(proposal.get_absolute_url())
    return "\n".join(
        (
            f"% {proposal.label}: {proposal.title}",
            f"% {url}",
            f"\\shortdesc{{{_description(sel)}}}",
            r"\begin{problem}",
            _indent(proposal.statement),
            r"\end{problem}",
            "",
            f"\\answer{{{proposal.answer:03d}}}",
            f"\\credits{{{_latex_text(proposal.credit_display)}}}",
            "",
            r"\begin{soln}",
            _indent(proposal.solution),
            r"\end{soln}",
            "",
        )
    )


def _order_tex(selections: Sequence[OIMESelection]) -> str:
    """A stub order file: every chosen problem, easiest first, for the EIC to shuffle."""
    ordered = sorted(
        selections, key=lambda sel: (sel.proposal.difficulty, sel.proposal.pk)
    )
    lines = [
        f"\\input{{problems/{sel.proposal.label}}}  % [{sel.proposal.subject}] {_description(sel)}"
        for sel in ordered
    ]
    return "\n".join(lines) + "\n"


def _mss(seconds: int | None) -> str:
    return "---" if seconds is None else f"{seconds // 60}:{seconds % 60:02d}"


def _testsolving_tex(selections: Sequence[OIMESelection]) -> str:
    r"""One ``\oimetestsolving`` line per chosen problem, read by ``oime-tables.tex``.

    The argument order must match the definition of ``\oimetestsolving`` there.

    Attempts and upvotes are recorded for the EIC but not shown in the table.
    """
    proposals = [sel.proposal for sel in selections]
    _attach_stats(proposals)
    lines = [
        r"% \oimetestsolving{label}{fastest}{median}{correct first try}"
        + r"{eventually correct}{attempts}{upvotes}"
    ]
    for p in proposals:
        st = p.stats  # type: ignore[attr-defined]
        fields = (
            p.label,
            _mss(st["fastest_seconds"]),
            _mss(st["median_seconds"]),
            str(st["first_correct"]),
            str(st["correct"]),
            str(st["total"]),
            str(p.upvote_count),  # type: ignore[attr-defined]
        )
        lines.append(
            "\\oimetestsolving" + "".join(f"{{{f}}}" for f in fields) + f"  % {p.title}"
        )
    return "\n".join(lines) + "\n"


def _solves_tex(selections: Sequence[OIMESelection]) -> str:
    r"""A stub for the contest results, which OTIS-WEB never sees.

    Its ``\oimesolves`` and ``\oimescore`` lines must match their definitions in
    ``oime-tables.tex``.
    """
    lines = [
        "% Fill these in from the contest results and uncomment them.",
        r"% \oimesolves{label}{number correct}",
    ]
    lines += [f"%\\oimesolves{{{sel.proposal.label}}}{{}}" for sel in selections]
    lines += ["", r"% \oimescore{total score}{frequency}"]
    lines += [f"%\\oimescore{{{k}}}{{}}" for k in range(len(selections) + 1)]
    return "\n".join(lines) + "\n"


def _acknow_tex(year: OIMEYear, selections: Sequence[OIMESelection]) -> str:
    """Proposers for the window and ranked testsolvers of the chosen problems.

    Testsolvers are listed most prolific first with their counts in comments, so
    the EIC can draw the tiers wherever they like. Contributors who asked to be
    left out of acknowledgments are left out.
    """
    proposals = [sel.proposal for sel in selections]
    proposers = set(
        OIMEProposal.objects.filter(
            is_draft=False,
            created_at__gte=year.proposals_open_at,
            created_at__lt=year.proposals_close_at,
            author__hide_from_acknowledgments=False,
        ).values_list("author__display_name", flat=True)
    )
    proposers.update(
        p.author.display_name
        for p in proposals
        if not p.author.hide_from_acknowledgments
    )
    completed = Q(fights__proposal__in=proposals) & ~Q(fights__status="OIME_TBD")
    testsolvers = (
        OIMEContributor.objects.filter(hide_from_acknowledgments=False)
        .annotate(n=Count("fights", filter=completed, distinct=True))
        .filter(n__gt=0)
        .order_by("-n", "display_name")
    )
    lines = [r"\subsection*{Problem proposers}"]
    lines += [f"{_latex_text(name)}," for name in sorted(proposers, key=str.casefold)]
    lines += ["", r"\subsection*{Testsolvers}"]
    lines += [
        f"{_latex_text(c.display_name)},  % {c.n} problems"  # type: ignore[attr-defined]
        for c in testsolvers
    ]
    return "\n".join(lines) + "\n"


@admin_required
def year_export(request: HttpRequest, pk: int) -> HttpResponse:
    """Everything the TeX repository needs from here, as one zip.

    It holds ``problems/``, ``originals/`` and ``data/``, to be pasted over a copy
    of last year's repository; the macros that read them live in that
    repository's ``oime-tables.tex``.

    This is the one-way handoff: after it, the repository owns the text and
    OTIS-WEB keeps the authors' originals.
    """
    year = get_object_or_404(OIMEYear, pk=pk)
    selections = list(_chosen(year))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for sel in selections:
            label = sel.proposal.label
            archive.writestr(f"problems/{label}.tex", _problem_tex(request, sel))
            archive.writestr(
                f"originals/{label}.tex", sel.proposal.statement.strip() + "\n"
            )
        archive.writestr("problems/order1.tex", _order_tex(selections))
        archive.writestr("problems/acknow.tex", _acknow_tex(year, selections))
        archive.writestr("data/testsolving.tex", _testsolving_tex(selections))
        archive.writestr("data/solves.tex", _solves_tex(selections))
    return HttpResponse(
        buffer.getvalue(),
        content_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="oime-{year.pk}.zip"'},
    )


@admin_required
def year_bulk_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Set the editor and description of every chosen problem on one page."""
    year = get_object_or_404(OIMEYear, pk=pk)
    formset = OIMEBulkEditFormSet(request.POST or None, queryset=_chosen(year))
    # Each row's editor dropdown would otherwise query every contributor again.
    if formset.forms:
        choices = list(formset.forms[0].fields["editor"].choices)  # type: ignore[attr-defined]
        for form in formset.forms:
            form.fields["editor"].choices = choices  # type: ignore[attr-defined]
    if request.method == "POST" and formset.is_valid():
        formset.save()
        messages.success(request, "Changes saved.")
        return redirect("oime-year-bulk-edit", year.pk)
    return render(
        request,
        "tubes/year_bulk_edit.html",
        {"year": year, "formset": formset},
    )
