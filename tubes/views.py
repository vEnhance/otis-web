import logging
from typing import Any

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView

from otisweb.decorators import verified_required
from otisweb.mixins import VerifiedRequiredMixin

from .forms import OIMEAnswerForm, OIMECommentForm, OIMEProposalForm, OIMESetupForm
from .models import (
    JoinRecord,
    OIMEAttempt,
    OIMEComment,
    OIMEContributor,
    OIMEParticipation,
    OIMEProposal,
    OIMEYear,
    Tube,
)

# ---------------------------------------------------------------------------
# Tube views (existing)
# ---------------------------------------------------------------------------


class TubeList(VerifiedRequiredMixin, ListView[Tube]):
    model = Tube
    context_object_name = "tube_list"
    template_name = "tubes/tube_list.html"

    def get_queryset(self) -> QuerySet[Tube]:
        return Tube.objects.filter(status="TB_ACTIVE")


@verified_required
def tube_join(request: HttpRequest, pk: int) -> HttpResponse:
    tube = get_object_or_404(Tube, pk=pk)
    if not tube.status == "TB_ACTIVE" or not tube.accepting_signups:
        raise PermissionDenied("Cannot join right now")
    try:
        jr = JoinRecord.objects.get(tube=tube, user=request.user)
    except JoinRecord.DoesNotExist:
        jr = JoinRecord.objects.filter(tube=tube, user__isnull=True).first()
        if jr is None:
            messages.error(
                request, "Ran out of one-time invite codes, please contact staff."
            )
            logging.critical(
                f"{tube} somehow ran out of one-time codes when {request.user} tried to join",
            )
            return HttpResponseRedirect(reverse("tube-list"))
        else:
            jr.user = request.user
            jr.activation_time = timezone.now()
            jr.save()
    return HttpResponseRedirect(jr.invite_url if jr.invite_url else jr.tube.main_url)


# ---------------------------------------------------------------------------
# OIME helpers
# ---------------------------------------------------------------------------


def _get_active_year() -> OIMEYear | None:
    return OIMEYear.objects.filter(active=True).first()


def _get_contributor(request: HttpRequest) -> OIMEContributor | None:
    try:
        return request.user.oime_contributor  # type: ignore[union-attr]
    except OIMEContributor.DoesNotExist:
        return None


def _get_participation(
    contributor: OIMEContributor, year: OIMEYear
) -> OIMEParticipation | None:
    try:
        return OIMEParticipation.objects.get(contributor=contributor, year=year)
    except OIMEParticipation.DoesNotExist:
        return None


def _get_solver_context(
    contributor: OIMEContributor,
    proposal: OIMEProposal,
    year: OIMEYear | None,
) -> dict[str, Any]:
    """Compute access flags for a contributor viewing a proposal."""
    participation: OIMEParticipation | None = None
    is_serious = False

    if year is not None:
        participation = _get_participation(contributor, year)
        if participation is not None:
            is_serious = participation.is_serious

    attempt: OIMEAttempt | None = None
    if is_serious:
        try:
            attempt = OIMEAttempt.objects.get(
                contributor=contributor, proposal=proposal
            )
            if attempt.status == "OIME_TBD" and attempt.time_expired:
                attempt.status = "OIME_TLE"
                attempt.submitted_at = timezone.now()
                attempt.save()
        except OIMEAttempt.DoesNotExist:
            pass

    can_see_solution = not is_serious or (attempt is not None and attempt.is_complete)
    can_comment = can_see_solution
    can_upvote = can_see_solution and contributor != proposal.author

    return {
        "year": year,
        "participation": participation,
        "is_serious": is_serious,
        "attempt": attempt,
        "can_see_solution": can_see_solution,
        "can_comment": can_comment,
        "can_upvote": can_upvote,
    }


# ---------------------------------------------------------------------------
# OIME: Setup / onboarding
# ---------------------------------------------------------------------------


@verified_required
def oime_setup(request: HttpRequest) -> HttpResponse:
    """First-time setup: create OIMEContributor and optionally enroll in active year."""
    contributor = _get_contributor(request)
    year = _get_active_year()

    if request.method == "POST":
        form = OIMESetupForm(request.POST)
        if form.is_valid():
            if contributor is None:
                contributor = OIMEContributor.objects.create(
                    user=request.user,  # type: ignore[union-attr]
                    display_name=form.cleaned_data["display_name"],
                )
            else:
                contributor.display_name = form.cleaned_data["display_name"]
                contributor.save()

            if year is not None:
                is_serious = form.cleaned_data["is_serious"] == "serious"
                participation, created = OIMEParticipation.objects.get_or_create(
                    contributor=contributor,
                    year=year,
                    defaults={"is_serious": is_serious},
                )
                if not created and participation.is_serious and not is_serious:
                    # Allow downgrade serious → casual only
                    participation.is_serious = False
                    participation.save()

            return redirect("oime-proposal-list")
    else:
        initial: dict[str, Any] = {}
        if contributor is not None:
            initial["display_name"] = contributor.display_name
            if year is not None:
                p = _get_participation(contributor, year)
                if p is not None:
                    initial["is_serious"] = "serious" if p.is_serious else "casual"
        form = OIMESetupForm(initial=initial)

    return render(
        request,
        "tubes/oime_setup.html",
        {
            "form": form,
            "contributor": contributor,
            "year": year,
            "is_edit": contributor is not None,
        },
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
        year = _get_active_year()
        context["contributor"] = contributor
        context["year"] = year

        if contributor is None:
            return context

        participation = _get_participation(contributor, year) if year else None
        context["participation"] = participation
        is_serious = participation is not None and participation.is_serious
        context["is_serious"] = is_serious

        if is_serious:
            user_attempts: dict[int, OIMEAttempt] = {
                a.proposal_id: a  # type: ignore[attr-defined]
                for a in OIMEAttempt.objects.filter(contributor=contributor)
            }
            for proposal in context["proposals"]:
                proposal.user_attempt = user_attempts.get(proposal.pk)  # type: ignore[attr-defined]

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
        context["submit_name"] = "Submit Proposal"
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

    year = _get_active_year()
    ctx = _get_solver_context(contributor, proposal, year)
    attempt: OIMEAttempt | None = ctx["attempt"]

    # Serious solver with an active attempt → go to the fight view
    if ctx["is_serious"] and attempt is not None and not attempt.is_complete:
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
        if ctx["can_see_solution"]
        else False
    )

    return render(
        request,
        "tubes/proposal_detail.html",
        {
            "proposal": proposal,
            "contributor": contributor,
            "answer_form": OIMEAnswerForm(),
            "comment_form": comment_form,
            "comments": comments,
            "has_upvoted": has_upvoted,
            **ctx,
        },
    )


@verified_required
def proposal_fight(request: HttpRequest, pk: int) -> HttpResponse:
    """Timed solving screen for serious testsolvers with an active attempt."""
    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    year = _get_active_year()
    ctx = _get_solver_context(contributor, proposal, year)
    attempt: OIMEAttempt | None = ctx["attempt"]

    # Only valid when there's an active in-progress serious attempt
    if not ctx["is_serious"] or attempt is None or attempt.is_complete:
        return redirect("oime-proposal-detail", pk)

    return render(
        request,
        "tubes/proposal_fight.html",
        {
            "proposal": proposal,
            "contributor": contributor,
            "attempt": attempt,
            "remaining_seconds": attempt.remaining_seconds,
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

    year = _get_active_year()
    if year is None:
        messages.error(request, "No active year for testsolving.")
        return redirect("oime-proposal-detail", pk)

    participation = _get_participation(contributor, year)
    if participation is None or not participation.is_serious:
        return redirect("oime-proposal-detail", pk)

    OIMEAttempt.objects.get_or_create(
        contributor=contributor,
        proposal=proposal,
        defaults={"year": year},
    )
    return redirect("oime-proposal-fight", pk)


@verified_required
def submit_answer(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("oime-proposal-detail", pk)

    proposal = get_object_or_404(OIMEProposal, pk=pk)
    contributor = _get_contributor(request)
    if contributor is None:
        return redirect("oime-setup")

    attempt = get_object_or_404(OIMEAttempt, contributor=contributor, proposal=proposal)

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
        if attempt.wrong_answers >= OIMEAttempt.ANSWER_LIMIT:
            attempt.status = "OIME_ALE"
            attempt.submitted_at = timezone.now()
            attempt.save()
            messages.error(
                request,
                f"Incorrect. You have used all {OIMEAttempt.ANSWER_LIMIT} attempts.",
            )
        else:
            attempt.save()
            remaining = OIMEAttempt.ANSWER_LIMIT - attempt.wrong_answers
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

    attempt = get_object_or_404(OIMEAttempt, contributor=contributor, proposal=proposal)

    if attempt.status == "OIME_TBD":
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

    year = _get_active_year()
    ctx = _get_solver_context(contributor, proposal, year)
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
