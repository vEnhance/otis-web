from typing import Any, Optional

from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models.query import QuerySet
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.views.generic.list import ListView

from otisweb.mixins import VerifiedRequiredMixin

from .forms import YearbookEntryCreateForm, YearbookEntryForm
from .models import YearbookEntry


def get_own_entry(user: User) -> Optional[YearbookEntry]:
    return YearbookEntry.objects.filter(user=user).first()


class YearbookList(VerifiedRequiredMixin, ListView[YearbookEntry]):
    model = YearbookEntry
    context_object_name = "entries"

    def get_queryset(self) -> QuerySet[YearbookEntry]:
        return YearbookEntry.objects.select_related("user")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        assert isinstance(self.request.user, User)
        context["own_entry"] = get_own_entry(self.request.user)
        return context


class YearbookDetail(VerifiedRequiredMixin, DetailView[YearbookEntry]):
    model = YearbookEntry
    context_object_name = "entry"
    slug_field = "user__username"
    slug_url_kwarg = "username"
    object: YearbookEntry

    def get_queryset(self) -> QuerySet[YearbookEntry]:
        return YearbookEntry.objects.select_related("user")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["is_own_entry"] = self.object.user.pk == self.request.user.pk
        return context


class YearbookCreate(
    VerifiedRequiredMixin, CreateView[YearbookEntry, YearbookEntryForm]
):
    model = YearbookEntry
    form_class = YearbookEntryCreateForm

    def existing_entry_redirect(self) -> Optional[HttpResponseRedirect]:
        """Nobody gets two entries; send repeat visitors to the edit form."""
        assert isinstance(self.request.user, User)
        if get_own_entry(self.request.user) is None:
            return None
        messages.info(
            self.request, "You already have a yearbook entry; here it is for editing."
        )
        return HttpResponseRedirect(reverse("yearbook-update"))

    def get(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.existing_entry_redirect() or super().get(request, *args, **kwargs)

    def post(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.existing_entry_redirect() or super().post(request, *args, **kwargs)

    def get_initial(self) -> dict[str, Any]:
        assert isinstance(self.request.user, User)
        initial = super().get_initial()
        initial["email"] = self.request.user.email
        return initial

    def form_valid(self, form: YearbookEntryForm) -> HttpResponse:
        assert isinstance(self.request.user, User)
        form.instance.user = self.request.user
        messages.success(self.request, "Welcome to the yearbook!")
        return super().form_valid(form)


class YearbookUpdate(
    VerifiedRequiredMixin, UpdateView[YearbookEntry, YearbookEntryForm]
):
    model = YearbookEntry
    form_class = YearbookEntryForm

    def get_object(self, queryset: Optional[QuerySet[Any]] = None) -> YearbookEntry:
        del queryset
        return get_object_or_404(YearbookEntry, user=self.request.user)

    def form_valid(self, form: YearbookEntryForm) -> HttpResponse:
        messages.success(self.request, "Updated your yearbook entry.")
        return super().form_valid(form)


class YearbookDelete(VerifiedRequiredMixin, DeleteView):
    model = YearbookEntry
    context_object_name = "entry"
    success_url = reverse_lazy("yearbook-list")

    def get_object(self, queryset: Optional[QuerySet[Any]] = None) -> YearbookEntry:
        del queryset
        return get_object_or_404(YearbookEntry, user=self.request.user)

    def form_valid(self, form: Any) -> HttpResponse:
        messages.success(self.request, "Removed your yearbook entry.")
        return super().form_valid(form)
