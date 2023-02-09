import logging
from typing import Any, ClassVar, Optional

import reversion
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http import Http404, HttpRequest, HttpResponseRedirect
from django.http.response import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from reversion.views import RevisionMixin

from arch.forms import ProblemSelectForm
from arch.models import get_disk_statement_from_puid
from core.utils import storage_hash
from evans_django_tools import ACTION_LOG_LEVEL
from otisweb.mixins import VerifiedRequiredMixin

from .forms import HintUpdateFormWithReason
from .models import Hint, Problem, Vote

ContextType = dict[str, Any]

logger = logging.getLogger(__name__)


class HintObjectView:
    kwargs: ClassVar[dict[str, Any]] = {}

    def get_object(self, queryset: Optional[QuerySet[Hint]] = None) -> Hint:
        if queryset is None:
            queryset = self.get_queryset()  # type: ignore
        assert queryset is not None
        return get_object_or_404(
            queryset, problem__puid=self.kwargs["puid"], number=self.kwargs["number"]
        )


class ProblemObjectView:
    kwargs: ClassVar[dict[str, Any]] = {}

    def get_object(self, queryset: Optional[QuerySet[Problem]] = None) -> Problem:
        if queryset is None:
            queryset = self.get_queryset()  # type: ignore
        assert queryset is not None
        return get_object_or_404(queryset, puid=self.kwargs["puid"])


class HintList(VerifiedRequiredMixin, ListView[Hint]):
    context_object_name = "hint_list"
    problem: Problem

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any):
        super().setup(request, *args, **kwargs)
        puid = kwargs["puid"]
        puid = puid.upper()
        try:
            self.problem = Problem.objects.get(puid=puid)
        except Problem.DoesNotExist:
            statement_exists_on_disk = get_disk_statement_from_puid(puid) is not None
            if kwargs["create_if_missing"] is True and statement_exists_on_disk:
                self.problem = Problem(puid=puid)
                self.problem.save()
                messages.info(request, f"Created previously nonexistent problem {puid}")
            elif statement_exists_on_disk:
                raise Http404("Need to log in to create problems")
            else:
                raise Http404(f"Couldn't find {puid} in database or disk")

    def get_queryset(self):
        return Hint.objects.filter(problem__puid=self.kwargs["puid"]).order_by("number")

    def get_context_data(self, **kwargs: dict[str, Any]):
        context = super().get_context_data(**kwargs)
        context["problem"] = self.problem
        context["statement"] = self.problem.get_statement()

        vote = Vote.objects.filter(user=self.request.user, problem=self.problem).first()

        if vote is not None:
            context["vote"] = vote.niceness
        return context


class HintDetail(HintObjectView, VerifiedRequiredMixin, DetailView[Hint]):
    context_object_name = "hint"
    model = Hint


class HintDetailByPK(VerifiedRequiredMixin, DetailView[Hint]):
    context_object_name = "hint"
    model = Hint


class HintUpdate(
    HintObjectView,
    VerifiedRequiredMixin,
    RevisionMixin,
    UpdateView[Hint, HintUpdateFormWithReason],
):
    context_object_name = "hint"
    model = Hint
    form_class = HintUpdateFormWithReason
    object: ClassVar[Hint] = Hint()  # type: ignore

    def form_valid(self, form: HintUpdateFormWithReason) -> HttpResponse:
        reversion.set_comment(
            form.cleaned_data["reason"] or form.cleaned_data["content"]
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> ContextType:
        context = super().get_context_data(**kwargs)
        context["problem"] = self.object.problem
        return context

    def get_success_url(self):
        return self.object.get_absolute_url()


class HintUpdateByPK(
    VerifiedRequiredMixin, RevisionMixin, UpdateView[Hint, HintUpdateFormWithReason]
):
    context_object_name = "hint"
    model = Hint
    form_class = HintUpdateFormWithReason
    object: ClassVar[Hint] = Hint()  # type: ignore

    def form_valid(self, form: HintUpdateFormWithReason) -> HttpResponse:
        reversion.set_comment(
            form.cleaned_data["reason"] or form.cleaned_data["content"]
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> ContextType:
        context = super().get_context_data(**kwargs)
        context["problem"] = self.object.problem
        return context

    def get_success_url(self):
        return self.object.get_absolute_url()


class ProblemUpdate(
    ProblemObjectView,
    VerifiedRequiredMixin,
    RevisionMixin,
    UpdateView[Problem, BaseModelForm[Problem]],
):
    context_object_name = "problem"
    model = Problem
    fields = (
        "puid",
        "hyperlink",
    )

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context["num_problems"] = Problem.objects.all().count()
        context["num_hints"] = Hint.objects.all().count()
        return context

    def form_valid(self, form: BaseModelForm[Problem]) -> HttpResponse:
        logger.log(
            ACTION_LOG_LEVEL,
            f"{form.instance.puid} was updated; "
            f"new hyperlink {form.instance.hyperlink}.",
        )
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return self.object.get_absolute_url()  # type: ignore


class HintCreate(
    VerifiedRequiredMixin, RevisionMixin, CreateView[Hint, BaseModelForm[Hint]]
):
    context_object_name = "hint"
    fields = (
        "problem",
        "number",
        "keywords",
        "content",
    )
    model = Hint

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context["problem"] = Problem.objects.get(puid=self.kwargs["puid"])
        return context

    def get_initial(self):
        initial = super().get_initial()
        initial = initial.copy()
        initial["problem"] = Problem.objects.get(puid=self.kwargs["puid"])
        return initial


class HintDelete(HintObjectView, VerifiedRequiredMixin, RevisionMixin, DeleteView):
    context_object_name = "hint"
    model = Hint
    object: ClassVar[Hint] = Hint()  # type: ignore

    def get_success_url(self):
        return reverse("hint-list", args=(self.object.problem.puid,))


# this is actually the index page as well :P bit of a hack I guess...
class ProblemCreate(
    VerifiedRequiredMixin,
    RevisionMixin,
    CreateView[Problem, BaseModelForm[Problem]],
):
    context_object_name = "problem"
    fields = (
        "puid",
        "hyperlink",
    )
    model = Problem
    template_name = "arch/index.html"

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context["lookup_form"] = ProblemSelectForm()
        context["num_problems"] = Problem.objects.all().count()
        context["num_hints"] = Hint.objects.all().count()
        context["lookup_url"] = reverse(
            "arch-lookup",
        )
        return context


@login_required
def lookup(request: HttpRequest):
    if request.method == "POST":
        form = ProblemSelectForm(request.POST)
        assert form.is_valid()
        problem = form.cleaned_data["problem"]
        return HttpResponseRedirect(problem.get_absolute_url())
    else:
        return HttpResponseRedirect(
            reverse(
                "arch-index",
            )
        )


@login_required
def view_solution(request: HttpRequest, puid: str):
    solution_target_name = "pdfs/" + storage_hash(puid) + ".tex"
    if default_storage.exists(solution_target_name):
        solution_url = default_storage.url(solution_target_name)
        return HttpResponseRedirect(solution_url)
    else:
        raise Http404


class VoteCreate(
    VerifiedRequiredMixin,
    CreateView[Vote, BaseModelForm[Vote]],
):
    context_object_name = "vote"
    fields = ("niceness",)
    model = Vote
    template_name = "arch/vote_form.html"

    def get_initial(self):
        self.problem = Problem.objects.get(puid=self.kwargs["puid"])

        initial = super().get_initial()
        initial = initial.copy()
        initial["problem"] = self.problem
        return initial

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context["problem"] = self.problem

        context["voted"] = Vote.objects.filter(
            user=self.request.user, problem=self.problem
        ).first()
        return context

    def form_valid(self, form: BaseModelForm[Vote]):
        messages.success(
            self.request, f"You rated {self.problem.puid} as {form.instance.niceness}"
        )

        voted = Vote.objects.filter(
            user=self.request.user, problem=self.problem
        ).first()
        if voted != None:
            voted.delete()

        form.instance.problem = self.problem
        form.instance.user = self.request.user

        return super().form_valid(form)

    def get_success_url(self):
        return self.problem.get_absolute_url()
