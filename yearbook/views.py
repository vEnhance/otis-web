import random
from typing import Any

from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models.query import QuerySet
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic.list import ListView

from otisweb.mixins import VerifiedRequiredMixin

from .forms import YearbookEntryForm
from .models import YearbookEntry

# The yearbook has outgrown a single page, so the full list is paginated and
# the index instead features a few entries at a time.
ENTRIES_PER_PAGE = 20
NUM_RANDOM_ENTRIES = 5


def get_own_entry(user: User) -> YearbookEntry | None:
    return YearbookEntry.objects.filter(user=user).first()


def entries_of_the_day(
    queryset: QuerySet[YearbookEntry], count: int = NUM_RANDOM_ENTRIES
) -> list[YearbookEntry]:
    """A sample of at most `count` entries drawn from `queryset`.

    Seeded on the current UTC date, so that the sample holds still for the day
    instead of reshuffling on every page load, and so that everyone browsing on
    the same day is looking at the same entries."""
    pks = sorted(queryset.values_list("pk", flat=True))
    rng = random.Random(timezone.now().date().toordinal())
    sampled = rng.sample(pks, min(count, len(pks)))
    return list(queryset.filter(pk__in=sampled))


class YearbookIndex(VerifiedRequiredMixin, TemplateView):
    """The yearbook's front page: a way in, rather than the whole yearbook.

    Everything here is either about the viewer (their own entry), a way to
    reach one particular entry (the picker, the link to the full list), or a
    handful of entries to look at."""

    template_name = "yearbook/yearbook_index.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        assert isinstance(user, User)

        # The picker lists everything this person is allowed to open, so the
        # count shown next to it counts the same set.
        visible = list(YearbookEntry.visible_to(user))
        context["all_entries"] = visible
        context["num_entries"] = len(visible)

        own_entry = get_own_entry(user)
        context["own_entry"] = own_entry
        # The list component takes an iterable, and the viewer's own entry is a
        # list of one so that it renders as a card like everything else.
        context["own_entries"] = [own_entry] if own_entry is not None else []

        # The featured sections are the same for everybody, so drafts stay out
        # of them: nobody's unfinished page gets shown off, not even to staff.
        published = YearbookEntry.objects.filter(is_draft=False).select_related("user")
        context["random_entries"] = entries_of_the_day(published)
        context["gm_entries"] = list(published.filter(user__is_superuser=True))
        return context


class YearbookList(VerifiedRequiredMixin, ListView[YearbookEntry]):
    model = YearbookEntry
    context_object_name = "entries"
    paginate_by = ENTRIES_PER_PAGE

    def get_queryset(self) -> QuerySet[YearbookEntry]:
        assert isinstance(self.request.user, User)
        return YearbookEntry.visible_to(self.request.user)


class YearbookDetail(VerifiedRequiredMixin, DetailView[YearbookEntry]):
    model = YearbookEntry
    context_object_name = "entry"
    object: YearbookEntry

    def get_queryset(self) -> QuerySet[YearbookEntry]:
        # Drafts 404 for everyone but their author and staff
        assert isinstance(self.request.user, User)
        return YearbookEntry.visible_to(self.request.user)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["is_own_entry"] = self.object.user.pk == self.request.user.pk
        return context


class YearbookCreate(
    VerifiedRequiredMixin, CreateView[YearbookEntry, YearbookEntryForm]
):
    model = YearbookEntry
    form_class = YearbookEntryForm

    def existing_entry_redirect(self) -> HttpResponseRedirect | None:
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

    def get_object(self, queryset: QuerySet[Any] | None = None) -> YearbookEntry:
        del queryset
        return get_object_or_404(YearbookEntry, user=self.request.user)

    def form_valid(self, form: YearbookEntryForm) -> HttpResponse:
        messages.success(self.request, "Updated your yearbook entry.")
        return super().form_valid(form)
