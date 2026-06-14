from datetime import timedelta
from typing import Any

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
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

GIVE_UP_RATE_LIMIT = 2  # max give-ups allowed within the window
GIVE_UP_WINDOW_MINUTES = 10


def _get_contributor(request: HttpRequest) -> OIMEContributor | None:
    try:
        return request.user.oime_contributor  # type: ignore[union-attr]
    except OIMEContributor.DoesNotExist:
        return None


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
    """
    is_author = contributor == proposal.author
    casual = _is_casual_for(contributor, proposal)

    if is_author:
        return {
            "is_author": True,
            "casual": casual,
            "fight": None,
            "can_see_statement": True,
            "can_see_solution": True,
            "can_start_fight": False,
            "can_comment": True,
            "can_upvote": True,
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

    if casual:
        can_see_solution = revealed or fight_complete
        return {
            "is_author": False,
            "casual": True,
            "fight": fight,
            "can_see_statement": True,
            "can_see_solution": can_see_solution,
            "can_start_fight": False,
            "can_comment": can_see_solution,
            "can_upvote": True,
        }

    # Ranked. Revealing a problem (escape hatch for someone who already knows it,
    # e.g. a co-author) forfeits the chance to fight it and spoils the solution.
    fight_active = fight is not None and not fight.is_complete
    can_see_solution = fight_complete or revealed
    return {
        "is_author": False,
        "casual": False,
        "fight": fight,
        "can_see_statement": fight_active or can_see_solution,
        "can_see_solution": can_see_solution,
        "can_start_fight": fight is None and not revealed,
        "can_comment": can_see_solution,
        "can_upvote": can_see_solution,
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
    first_correct = [f for f in correct if f.wrong_answers == 0]
    clean = [f for f in first_correct if f.solve_time_seconds is not None]
    fastest_clean = min(clean, key=lambda f: f.solve_time_seconds) if clean else None  # type: ignore[arg-type, return-value]

    def pct(n: int) -> int:
        return round(100 * n / total) if total else 0

    return {
        "total": total,
        "correct": len(correct),
        "correct_pct": pct(len(correct)),
        "first_correct": len(first_correct),
        "first_correct_pct": pct(len(first_correct)),
        "fastest_clean": fastest_clean,
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
    from django import forms as django_forms

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
                "You have an active fight in progress. Finish or give up first.",
            )
            return redirect("oime-casual")
        contributor.casual_mode = True
        contributor.save()
        messages.success(
            request,
            "You are now in casual mode. Browse and try any problem untimed and "
            "upvote ones you like; solutions stay hidden until you reveal them.",
        )
        return redirect("oime-proposal-list")
    return render(
        request,
        "tubes/oime_casual_confirm.html",
        {"form": django_forms.Form(), "has_active_fight": has_active_fight},
    )


@verified_required
def go_serious(request: HttpRequest) -> HttpResponse:
    """Confirmation page and action for returning to ranked mode from casual mode."""
    from django import forms as django_forms

    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")
    if not contributor.casual_mode:
        return redirect("oime-proposal-list")
    if request.method == "POST":
        contributor.casual_mode = False
        contributor.ranked_cutoff = timezone.now()
        contributor.save()
        messages.success(
            request,
            "You are back in ranked mode. Problems added from now on are eligible for "
            "timed solving; everything that already exists stays browsable casually.",
        )
        return redirect("oime-proposal-list")
    return render(
        request,
        "tubes/oime_serious_confirm.html",
        {"form": django_forms.Form()},
    )


# ---------------------------------------------------------------------------
# OIME: Proposal list / create / update
# ---------------------------------------------------------------------------


class ProposalListView(VerifiedRequiredMixin, ListView[OIMEProposal]):
    model = OIMEProposal
    template_name = "tubes/proposal_list.html"
    context_object_name = "proposals"

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:  # type: ignore[union-attr]
            return redirect("account_login")
        if _get_contributor(request) is None:
            return redirect("oime-setup")
        return super().dispatch(request, *args, **kwargs)  # type: ignore[return-value]

    def get_queryset(self) -> QuerySet[OIMEProposal]:
        user = self.request.user
        qs = (
            OIMEProposal.objects.select_related("author")
            .annotate(upvote_count=Count("upvotes", distinct=True))
            .order_by("-created_at")
        )
        # Staff see all; others see non-archived plus their own archived
        if not user.is_staff:  # type: ignore[union-attr]
            contributor = _get_contributor(self.request)
            if contributor is not None:
                qs = qs.filter(archived=False) | qs.filter(author=contributor)
            else:
                qs = qs.filter(archived=False)
        return qs.distinct()

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        contributor = _get_contributor(self.request)
        context["contributor"] = contributor

        if contributor is None:
            return context

        context["casual"] = contributor.casual_mode

        user_fights: dict[int, OIMEFight] = {
            f.proposal_id: f  # type: ignore[attr-defined]
            for f in OIMEFight.objects.filter(contributor=contributor)
        }
        revealed_ids = set(contributor.revealed_proposals.values_list("pk", flat=True))

        own: list[OIMEProposal] = []
        browse: list[OIMEProposal] = []
        unsolved: list[OIMEProposal] = []
        completed: list[OIMEProposal] = []

        for proposal in context["proposals"]:
            fight = user_fights.get(proposal.pk)
            proposal.user_fight = fight  # type: ignore[attr-defined]
            if contributor == proposal.author:
                proposal.user_list_status = "author"  # type: ignore[attr-defined]
                own.append(proposal)
            elif fight is not None and fight.is_complete:
                # A finished fight is a real recorded result, in any mode.
                proposal.user_list_status = "completed"  # type: ignore[attr-defined]
                completed.append(proposal)
            elif _is_casual_for(contributor, proposal):
                proposal.user_list_status = (  # type: ignore[attr-defined]
                    "revealed" if proposal.pk in revealed_ids else "casual"
                )
                browse.append(proposal)
            elif proposal.pk in revealed_ids:
                # Ranked, but spoiled via the escape hatch → no longer fightable.
                proposal.user_list_status = "revealed"  # type: ignore[attr-defined]
                browse.append(proposal)
            elif fight is not None:
                proposal.user_list_status = "in_progress"  # type: ignore[attr-defined]
                unsolved.append(proposal)
            else:
                proposal.user_list_status = "not_started"  # type: ignore[attr-defined]
                unsolved.append(proposal)

        context["own_proposals"] = own
        context["browse_proposals"] = browse
        context["unsolved_proposals"] = unsolved
        context["completed_proposals"] = completed

        return context


class ProposalCreateView(
    VerifiedRequiredMixin, CreateView[OIMEProposal, OIMEProposalForm]
):
    model = OIMEProposal
    form_class = OIMEProposalForm
    template_name = "tubes/proposal_form.html"

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:  # type: ignore[union-attr]
            return redirect("account_login")
        if _get_contributor(request) is None:
            return redirect("oime-setup")
        return super().dispatch(request, *args, **kwargs)  # type: ignore[return-value]

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
def proposal_detail(request: HttpRequest, pk: int) -> HttpResponse:
    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    ctx = _get_solver_context(contributor, proposal)
    fight: OIMEFight | None = ctx["fight"]

    # Ranked contributor with an active fight → send to the timed fight view
    if not ctx["casual"] and fight is not None and not fight.is_complete:
        return redirect("oime-proposal-fight", pk)

    comment_form = OIMECommentForm()

    if request.method == "POST":
        if "submit_comment" in request.POST:
            if not ctx["can_comment"]:
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
    # Show the testsolve stats summary to anyone who can no longer fight the problem.
    stats = None if ctx["can_start_fight"] else _proposal_stats(proposal)

    return render(
        request,
        "tubes/proposal_detail.html",
        {
            "proposal": proposal,
            "contributor": contributor,
            "comment_form": comment_form,
            "comments": comments,
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

    ctx = _get_solver_context(contributor, proposal)
    fight: OIMEFight | None = ctx["fight"]

    # Only valid while there is an active, in-progress fight (ranked mode only)
    if ctx["casual"] or fight is None or fight.is_complete:
        return redirect("oime-proposal-detail", pk)

    return render(
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


@verified_required
def start_attempt(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("oime-proposal-detail", pk)

    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    ctx = _get_solver_context(contributor, proposal)
    if not ctx["can_start_fight"]:
        messages.error(request, "You cannot start a new fight on this problem.")
        return redirect("oime-proposal-detail", pk)

    if OIMEFight.objects.filter(contributor=contributor, status="OIME_TBD").exists():
        messages.error(request, "You already have an active fight in progress.")
        return redirect("oime-proposal-detail", pk)

    OIMEFight.objects.create(contributor=contributor, proposal=proposal)
    return redirect("oime-proposal-fight", pk)


@verified_required
def submit_answer(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("oime-proposal-detail", pk)

    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    attempt = get_object_or_404(OIMEFight, contributor=contributor, proposal=proposal)

    if attempt.status != "OIME_TBD":
        return redirect("oime-proposal-detail", pk)

    if attempt.time_expired:
        attempt.status = "OIME_TLE"
        attempt.submitted_at = timezone.now()
        attempt.save()
        messages.warning(request, "Time's up!")
        return redirect("oime-proposal-detail", pk)

    form = OIMEAnswerForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please enter a valid integer (0-999).")
        return redirect("oime-proposal-fight", pk)

    submitted = form.cleaned_data["answer"]
    if submitted == proposal.answer:
        elapsed = int((timezone.now() - attempt.started_at).total_seconds())
        attempt.status = "OIME_OK"
        attempt.submitted_at = timezone.now()
        attempt.solve_time_seconds = elapsed
        attempt.save()
        messages.success(request, "Correct! Great job!")
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
                f"Incorrect (wrong answer #{attempt.wrong_answers}). {remaining} attempt{'' if remaining == 1 else 's'} remaining.",
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

    attempt = get_object_or_404(OIMEFight, contributor=contributor, proposal=proposal)

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

    ctx = _get_solver_context(contributor, proposal)
    if not ctx["can_upvote"]:
        raise PermissionDenied

    if proposal.upvotes.filter(pk=contributor.pk).exists():
        proposal.upvotes.remove(contributor)
    else:
        proposal.upvotes.add(contributor)

    return redirect("oime-proposal-detail", pk)


@verified_required
def proposal_results(request: HttpRequest, pk: int) -> HttpResponse:
    """Leaderboard of every fight on a problem, for contributors who can no longer fight it."""
    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

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
            f.solve_time_seconds if f.solve_time_seconds is not None else 1_000_000,
        )
    )

    return render(
        request,
        "tubes/proposal_results.html",
        {
            "proposal": proposal,
            "contributor": contributor,
            "fights": fights,
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


class LandingView(TemplateView):
    template_name = "tubes/landing.html"
