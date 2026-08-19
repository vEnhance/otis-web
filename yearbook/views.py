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
    """The first `count` published entries of a shuffle of `queryset`.

    Everything about the draw is pinned to the current UTC day, so that the
    entries somebody sees this morning are still there this evening: the seed
    is today's date, and the entries taking part are the ones that already
    existed when the day started.

    That way, what other people do today cannot reshuffle today's draw.
    Somebody signing the yearbook this afternoon would otherwise change
    everyone else's five; instead their entry joins the shuffle tomorrow.
    Drafts take part in the shuffle too, and are skipped when reading the five
    off the front of it, so that taking your own entry out of the yearbook
    leaves everyone else's where they were rather than dealing a new hand."""
    day_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    # The pk list has to be read out anyway to shuffle it, so `is_draft` comes
    # along for the ride rather than costing a query of its own.
    rows = sorted(
        queryset.filter(created_at__lt=day_start).values_list("pk", "is_draft")
    )
    random.Random(day_start.date().toordinal()).shuffle(rows)
    pks = [pk for pk, is_draft in rows if not is_draft][:count]
    return list(queryset.filter(pk__in=pks))


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
        entries = YearbookEntry.objects.select_related("user")
        context["random_entries"] = entries_of_the_day(entries)
        context["gm_entries"] = list(
            entries.filter(is_draft=False, user__is_superuser=True)
        )
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
