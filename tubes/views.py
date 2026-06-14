from datetime import timedelta
from typing import Any

from django.contrib import messages
from django.core.exceptions import PermissionDenied
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


def _get_solver_context(
    contributor: OIMEContributor,
    proposal: OIMEProposal,
) -> dict[str, Any]:
    """Compute spoil status and access flags for a contributor viewing a proposal.

    A contributor is *spoiled* on a proposal if any of the following hold:
    - They are the proposal's author.
    - Their ``spoil_before`` timestamp is set and is >= the proposal's creation time.
    - They have a completed attempt on the proposal.

    Spoiled contributors can see the statement, answer, solution, and discussion.
    Unspoiled contributors see the statement only while actively fighting (proposal_fight).
    """
    is_author = contributor == proposal.author

    if is_author:
        return {
            "is_spoiled": True,
            "is_author": True,
            "fight": None,
            "can_start_fight": False,
            "can_comment": True,
            "can_upvote": False,
        }

    is_globally_spoiled = (
        contributor.spoil_before is not None
        and proposal.created_at <= contributor.spoil_before
    )

    fight: OIMEFight | None = None
    try:
        fight = OIMEFight.objects.get(contributor=contributor, proposal=proposal)
        if fight.status == "OIME_TBD" and fight.time_expired:
            fight.status = "OIME_TLE"
            fight.submitted_at = timezone.now()
            fight.save()
    except OIMEFight.DoesNotExist:
        pass

    is_spoiled = is_globally_spoiled or (fight is not None and fight.is_complete)

    return {
        "is_spoiled": is_spoiled,
        "is_author": False,
        "fight": fight,
        "can_start_fight": not is_spoiled and fight is None,
        "can_comment": is_spoiled,
        "can_upvote": is_spoiled,
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
def spoil_self(request: HttpRequest) -> HttpResponse:
    """Confirmation page and action for spoiling oneself on all current proposals."""
    from django import forms as django_forms

    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")
    if contributor.spoil_before is not None:
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
            return redirect("oime-spoil")
        contributor.spoil_before = timezone.now()
        contributor.save()
        messages.success(
            request,
            "You are now spoiled on all problems created up to this moment "
            "and can browse their statements and solutions freely.",
        )
        return redirect("oime-proposal-list")
    return render(
        request,
        "tubes/oime_spoil_confirm.html",
        {"form": django_forms.Form(), "has_active_fight": has_active_fight},
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
        qs = OIMEProposal.objects.select_related("author").order_by("-created_at")
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

        context["spoil_before"] = contributor.spoil_before

        user_fights: dict[int, OIMEFight] = {
            f.proposal_id: f  # type: ignore[attr-defined]
            for f in OIMEFight.objects.filter(contributor=contributor)
        }

        own: list[OIMEProposal] = []
        unspoiled: list[OIMEProposal] = []
        completed: list[OIMEProposal] = []
        globally_spoiled: list[OIMEProposal] = []

        for proposal in context["proposals"]:
            fight = user_fights.get(proposal.pk)
            proposal.user_fight = fight  # type: ignore[attr-defined]
            if contributor == proposal.author:
                proposal.user_list_status = "author"  # type: ignore[attr-defined]
                own.append(proposal)
            elif fight is not None and fight.is_complete:
                proposal.user_list_status = "completed"  # type: ignore[attr-defined]
                completed.append(proposal)
            elif (
                contributor.spoil_before is not None
                and proposal.created_at <= contributor.spoil_before
            ):
                proposal.user_list_status = "spoiled"  # type: ignore[attr-defined]
                globally_spoiled.append(proposal)
            elif fight is not None:
                proposal.user_list_status = "in_progress"  # type: ignore[attr-defined]
                unspoiled.append(proposal)
            else:
                proposal.user_list_status = "not_started"  # type: ignore[attr-defined]
                unspoiled.append(proposal)

        context["own_proposals"] = own
        context["unspoiled_proposals"] = unspoiled
        context["completed_proposals"] = completed
        context["globally_spoiled_proposals"] = globally_spoiled

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

    # Unspoiled contributor with an active fight → send to the fight view
    if not ctx["is_spoiled"] and fight is not None and not fight.is_complete:
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
        if ctx["is_spoiled"]
        else None
    )
    has_upvoted = (
        proposal.upvotes.filter(pk=contributor.pk).exists()
        if ctx["is_spoiled"]
        else False
    )

    return render(
        request,
        "tubes/proposal_detail.html",
        {
            "proposal": proposal,
            "contributor": contributor,
            "comment_form": comment_form,
            "comments": comments,
            "has_upvoted": has_upvoted,
            **ctx,
        },
    )


@verified_required
def proposal_fight(request: HttpRequest, pk: int) -> HttpResponse:
    """Timed solving screen for an unspoiled contributor with an active attempt."""
    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    ctx = _get_solver_context(contributor, proposal)
    fight: OIMEFight | None = ctx["fight"]

    # Only valid while there is an active, in-progress fight and the user isn't spoiled
    if ctx["is_spoiled"] or fight is None or fight.is_complete:
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
