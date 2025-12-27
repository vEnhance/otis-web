from typing import Any

from braces.views import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.urls.base import reverse_lazy
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.views.generic.list import ListView

from core.models import Unit
from otisweb.mixins import VerifiedRequiredMixin

from .models import ProblemSuggestion


class ProblemSuggestionCreate(
    VerifiedRequiredMixin,
    CreateView[ProblemSuggestion, BaseModelForm[ProblemSuggestion]],
):
    context_object_name = "problem_suggestion"
    fields = (
        "unit",
        "weight",
        "source",
        "hyperlink",
        "description",
        "statement",
        "solution",
        "comments",
        "acknowledge",
    )
    model = ProblemSuggestion

    def get_form(self, *args: Any, **kwargs: Any) -> BaseModelForm[ProblemSuggestion]:
        form = super().get_form(*args, **kwargs)
        form.fields["unit"].queryset = Unit.objects.filter(group__hidden=False)  # type: ignore
        return form

    def get_initial(self):
        initial = super().get_initial()
        uid = self.kwargs.get("unit_pk", None)
        if uid is not None:
            unit = get_object_or_404(Unit, pk=uid)
            if unit.group.hidden is False:
                initial["unit"] = uid
        return initial

    def form_valid(self, form: BaseModelForm[ProblemSuggestion]):
        form.instance.user = self.request.user
        messages.success(
            self.request,
            "Successfully submitted suggestion! Thanks much :) You can add more using the form below.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("suggest-new", kwargs=self.kwargs)


class ProblemSuggestionUpdate(
    LoginRequiredMixin, UpdateView[ProblemSuggestion, BaseModelForm[ProblemSuggestion]]
):
    context_object_name = "suggestion"
    fields = (
        "unit",
        "weight",
        "source",
        "hyperlink",
        "description",
        "statement",
        "solution",
        "comments",
        "acknowledge",
    )
    model = ProblemSuggestion
    object: ProblemSuggestion

    def get_success_url(self):
        return reverse("suggest-update", kwargs=self.kwargs)

    def form_valid(self, form: BaseModelForm[ProblemSuggestion]):
        self.object.status = "SUGG_NEW"
        messages.success(self.request, "Edits saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        assert isinstance(self.request.user, User)
        if not (self.request.user.is_staff or self.request.user == self.object.user):
            raise PermissionDenied("Logged-in user cannot view this suggestion")

        context["pk"] = self.kwargs.get("pk", None)
        return context


class ProblemSuggestionDelete(LoginRequiredMixin, DeleteView):
    model = ProblemSuggestion
    success_url = reverse_lazy("suggest-new")

    context_object_name = "suggestion"

    def get_object(self, *args: Any, **kwargs: Any) -> ProblemSuggestion:
        obj = super().get_object(*args, **kwargs)
        assert isinstance(self.request.user, User)
        if obj.user != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("Not authorized to delete this file")
        return obj


class ProblemSuggestionList(LoginRequiredMixin, ListView[ProblemSuggestion]):
    context_object_name = "problem_suggestions"

    def get_queryset(self):
        queryset = ProblemSuggestion.objects.filter(user=self.request.user)
        queryset = queryset.order_by("status", "created_at")
        return queryset


class SuggestionQueueList(LoginRequiredMixin, ListView[ProblemSuggestion]):
    template_name = "suggestions/suggestion_queue_list.html"
    context_object_name = "suggestions"

    def get_queryset(self) -> QuerySet[ProblemSuggestion]:
        return ProblemSuggestion.objects.filter(status="SUGG_NEW").order_by(
            "updated_at"
        )
