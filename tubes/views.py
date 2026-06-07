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

from .forms import OIMEAnswerForm, OIMECommentForm, OIMEProposalForm
from .models import JoinRecord, OIMEAttempt, OIMEComment, OIMEProposal, OIMESolverRole, Tube


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
            # we ran out of valid codes to give fml
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


class ProposalListView(VerifiedRequiredMixin, ListView[OIMEProposal]):
    model = OIMEProposal
    template_name = "tubes/proposal_list.html"
    context_object_name = "proposals"

    def get_queryset(self) -> QuerySet[OIMEProposal]:
        return OIMEProposal.objects.select_related("author").order_by("-created_at")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        try:
            role = user.oime_role  # type: ignore[union-attr]
            context["is_serious"] = role.is_serious
            context["role_set"] = True
        except OIMESolverRole.DoesNotExist:
            context["is_serious"] = False
            context["role_set"] = False

        if context["is_serious"]:
            user_attempts: dict[int, OIMEAttempt] = {
                a.proposal_id: a  # type: ignore[attr-defined]
                for a in OIMEAttempt.objects.filter(user=user)
            }
            for proposal in context["proposals"]:
                proposal.user_attempt = user_attempts.get(proposal.pk)  # type: ignore[attr-defined]
        return context


class ProposalCreateView(VerifiedRequiredMixin, CreateView[OIMEProposal, OIMEProposalForm]):
    model = OIMEProposal
    form_class = OIMEProposalForm
    template_name = "tubes/proposal_form.html"

    def form_valid(self, form: OIMEProposalForm) -> HttpResponse:
        form.instance.author = self.request.user  # type: ignore[union-attr]
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["action"] = "Submit"
        return context


class ProposalUpdateView(VerifiedRequiredMixin, UpdateView[OIMEProposal, OIMEProposalForm]):
    model = OIMEProposal
    form_class = OIMEProposalForm
    template_name = "tubes/proposal_form.html"

    def get_object(self, queryset: QuerySet[OIMEProposal] | None = None) -> OIMEProposal:
        proposal = super().get_object(queryset)
        if proposal.author != self.request.user and not self.request.user.is_staff:  # type: ignore[union-attr]
            raise PermissionDenied("You can only edit your own proposals.")
        return proposal

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["action"] = "Update"
        return context


@verified_required
def role_select(request: HttpRequest) -> HttpResponse:
    try:
        role = request.user.oime_role  # type: ignore[union-attr]
    except OIMESolverRole.DoesNotExist:
        role = None

    if request.method == "POST":
        is_serious = request.POST.get("role") == "serious"
        if role is None:
            OIMESolverRole.objects.create(user=request.user, is_serious=is_serious)  # type: ignore[union-attr]
        else:
            role.is_serious = is_serious
            role.save()
        return redirect("oime-proposal-list")

    return render(request, "tubes/role_select.html", {"role": role})


def _get_solver_context(user: Any, proposal: OIMEProposal) -> dict[str, Any]:
    try:
        is_serious = user.oime_role.is_serious
    except OIMESolverRole.DoesNotExist:
        is_serious = False

    attempt: OIMEAttempt | None = None
    if is_serious:
        try:
            attempt = OIMEAttempt.objects.get(user=user, proposal=proposal)
            if attempt.status == "IN_PROGRESS" and attempt.time_expired:
                attempt.status = "GAVE_UP"
                attempt.submitted_at = timezone.now()
                attempt.save()
        except OIMEAttempt.DoesNotExist:
            pass

    can_see_solution = not is_serious or (attempt is not None and attempt.is_complete)
    can_comment = can_see_solution and (
        user == proposal.author
        or user.is_staff
        or (attempt is not None and attempt.is_complete)
        or not is_serious
    )

    return {
        "is_serious": is_serious,
        "attempt": attempt,
        "can_see_solution": can_see_solution,
        "can_comment": can_comment,
    }


@verified_required
def proposal_detail(request: HttpRequest, pk: int) -> HttpResponse:
    proposal = get_object_or_404(OIMEProposal, pk=pk)
    user = request.user

    ctx = _get_solver_context(user, proposal)
    attempt: OIMEAttempt | None = ctx["attempt"]

    comment_form = OIMECommentForm()
    answer_form = OIMEAnswerForm()

    if request.method == "POST":
        if "submit_comment" in request.POST:
            if not ctx["can_comment"]:
                raise PermissionDenied
            comment_form = OIMECommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.author = user  # type: ignore[union-attr]
                comment.proposal = proposal
                comment.save()
                return redirect("oime-proposal-detail", pk=pk)

    remaining_seconds = attempt.remaining_seconds if (attempt and not attempt.is_complete) else None
    comments = (
        OIMEComment.objects.filter(proposal=proposal).select_related("author")
        if ctx["can_see_solution"]
        else None
    )

    return render(
        request,
        "tubes/proposal_detail.html",
        {
            "proposal": proposal,
            "answer_form": answer_form,
            "comment_form": comment_form,
            "comments": comments,
            "remaining_seconds": remaining_seconds,
            **ctx,
        },
    )


@verified_required
def start_attempt(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("oime-proposal-detail", pk=pk)
    proposal = get_object_or_404(OIMEProposal, pk=pk)
    OIMEAttempt.objects.get_or_create(user=request.user, proposal=proposal)  # type: ignore[union-attr]
    return redirect("oime-proposal-detail", pk=pk)


@verified_required
def submit_answer(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("oime-proposal-detail", pk=pk)

    proposal = get_object_or_404(OIMEProposal, pk=pk)
    attempt = get_object_or_404(OIMEAttempt, user=request.user, proposal=proposal)

    if attempt.status != "IN_PROGRESS":
        return redirect("oime-proposal-detail", pk=pk)

    if attempt.time_expired:
        attempt.status = "GAVE_UP"
        attempt.submitted_at = timezone.now()
        attempt.save()
        messages.warning(request, "Time's up! The problem has been marked as gave up.")
        return redirect("oime-proposal-detail", pk=pk)

    form = OIMEAnswerForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please enter a valid integer (0-999).")
        return redirect("oime-proposal-detail", pk=pk)

    submitted = form.cleaned_data["answer"]
    if submitted == proposal.answer:
        elapsed = int((timezone.now() - attempt.started_at).total_seconds())
        attempt.status = "CORRECT"
        attempt.submitted_at = timezone.now()
        attempt.solve_time_seconds = elapsed
        attempt.save()
        messages.success(request, "Correct! Great job!")
    else:
        attempt.wrong_answers += 1
        attempt.save()
        messages.error(request, f"Incorrect (wrong answer #{attempt.wrong_answers}). Try again!")

    return redirect("oime-proposal-detail", pk=pk)


@verified_required
def give_up(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("oime-proposal-detail", pk=pk)

    proposal = get_object_or_404(OIMEProposal, pk=pk)
    attempt = get_object_or_404(OIMEAttempt, user=request.user, proposal=proposal)

    if attempt.status == "IN_PROGRESS":
        attempt.status = "GAVE_UP"
        attempt.submitted_at = timezone.now()
        attempt.save()
        messages.info(request, "You gave up on this problem. You can now view the solution.")

    return redirect("oime-proposal-detail", pk=pk)
