import statistics
from collections.abc import Sequence
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

from otisweb.decorators import verified_required
from otisweb.mixins import VerifiedRequiredMixin

from .forms import (
    OIMEAnswerForm,
    OIMECommentForm,
    OIMEContributorForm,
    OIMEProposalForm,
)
from .models import OIMEComment, OIMEContributor, OIMEFight, OIMEProposal

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


def _deny_if_archived(
    request: HttpRequest,
    proposal: OIMEProposal,
    contributor: OIMEContributor | None,
) -> None:
    """Raise unless the viewer may see ``proposal``, which may be archived.

    Archiving is staff pulling a problem out of circulation, so an archived problem
    is readable only by staff and by its author; it is also frozen, in that nobody
    starts a session on it, upvotes it or comments on it any more (see
    :func:`_get_solver_context`).

    As with drafts, a contributor who already started a session keeps read access.
    Nothing is hidden from them that they have not already seen, and locking them
    out would strand an attempt with the clock still running and no way to submit
    or give up.
    """
    if not proposal.archived:
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
            f"{proposal.label} has been archived by staff. You keep access because "
            "you already started a session on it.",
        )
        return
    raise PermissionDenied("This proposal has been archived.")


def _deny_if_hidden(
    request: HttpRequest,
    proposal: OIMEProposal,
    contributor: OIMEContributor | None,
) -> None:
    """Raise unless the viewer may see ``proposal`` at all.

    Every per-proposal view starts here, so that a problem withdrawn from the
    listings — as a draft or as archived — cannot be reached by URL either.
    """
    _deny_if_draft(request, proposal, contributor)
    _deny_if_archived(request, proposal, contributor)


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

    An archived problem is frozen on top of all that: staff pulled it out of
    circulation, so no one starts a session on it or upvotes it any more, however
    they came to still have read access to it.
    """
    is_author = contributor == proposal.author
    casual = _is_casual_for(contributor, proposal)
    frozen = proposal.archived

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
    total = len(fights)
    correct = [f for f in fights if f.status == "OIME_OK"]
    first_correct = [
        f for f in correct if f.wrong_answers == 0 and f.submitted_at is not None
    ]

    def _elapsed(f: OIMEFight) -> int:
        return int((f.submitted_at - f.started_at).total_seconds())  # type: ignore[operator]

    fastest_clean = min(first_correct, key=_elapsed) if first_correct else None

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
        "median_clean": median_clean,
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
        OIMEProposal.objects.filter(archived=False, is_draft=False, subject=subject)
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
        # Archived proposals are hidden from everyone, authors and staff
        # included; use the Django admin to browse them. Drafts are hidden the
        # same way here, but their authors can find them on the drafts page.
        return (
            OIMEProposal.objects.filter(archived=False, is_draft=False)
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
        return initial

    def form_valid(self, form: OIMEProposalForm) -> HttpResponse:
        contributor = _get_contributor(self.request)
        if contributor is None:
            return redirect("oime-setup")
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
        is_author = contributor is not None and proposal.author == contributor
        if not is_author and not self.request.user.is_staff:  # type: ignore[union-attr]
            raise PermissionDenied("You can only edit your own proposals.")
        return proposal

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
    # The discussion on an archived problem is frozen along with the rest of it.
    can_comment = ctx["can_see_solution"] and not proposal.archived

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
            **ctx,
        },
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
            int((f.submitted_at - f.started_at).total_seconds())
            if f.status == "OIME_OK" and f.submitted_at is not None
            else 1_000_000,
        )
    )

    return render(
        request,
        "tubes/proposal_results.html",
        {
            "proposal": proposal,
            "contributor": contributor,
            "fights": fights,
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
    # An archived problem's discussion is frozen, so its comments are read-only too.
    if comment.proposal.archived:
        raise PermissionDenied("This proposal has been archived.")

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
        if contributor is None:
            return context

        recent = list(
            OIMEProposal.objects.filter(archived=False, is_draft=False)
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
