from typing import Any

from braces.views import LoginRequiredMixin
from core.models import Unit
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.forms.models import BaseModelForm
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic.list import ListView

from .models import ProblemSuggestion


class ProblemSuggestionCreate(
    LoginRequiredMixin, CreateView[ProblemSuggestion, BaseModelForm[ProblemSuggestion]]
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
        form = super(CreateView, self).get_form(*args, **kwargs)
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
        if not isinstance(self.request.user, User):
            raise PermissionDenied("Please log in")
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
        if not isinstance(self.request.user, User):
            raise PermissionDenied("Please log in.")
        if not (self.request.user.is_staff or self.request.user == self.object.user):
            raise PermissionDenied("Logged-in user cannot view this suggestion")
        return context


class ProblemSuggestionList(LoginRequiredMixin, ListView[ProblemSuggestion]):
    context_object_name = "problem_suggestions"

    def get_queryset(self):
        if not isinstance(self.request.user, User):
            raise PermissionDenied("Please log in.")
        queryset = ProblemSuggestion.objects.filter(user=self.request.user)
        queryset = queryset.order_by("status", "created_at")
        return queryset
