from typing import Any, Optional

from braces.views import LoginRequiredMixin, SuperuserRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.db.models.aggregates import Count
from django.db.models.base import Model
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.forms.models import BaseModelForm
from django.http import HttpRequest, HttpResponse
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls.base import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic.edit import UpdateView
from django.views.generic.list import ListView
from sql_util.utils import Exists

from core.models import UserProfile
from dashboard.models import PSet, UploadedFile
from otisweb.utils import AuthHttpRequest
from roster.models import Student

from .models import Unit, UnitGroup
from .utils import get_from_google_storage

# Create your views here.


class AdminUnitListView(SuperuserRequiredMixin, ListView[Unit]):
    model = Unit
    queryset = Unit.objects.all()
    template_name = "core/admin_unit_list.html"
    context_object_name = "unit_list"


class UnitGroupListView(ListView[Unit]):
    model = Unit
    context_object_name = "units"

    def get_queryset(self):
        queryset = Unit.objects.filter(group__hidden=False)
        queryset = queryset.order_by("group__subject", "group__name", "code")
        queryset = queryset.annotate(num_psets_in_group=Count("group__unit__pset"))

        if not isinstance(self.request.user, AnonymousUser):
            queryset = queryset.annotate(
                has_pset=Exists(
                    "pset",
                    filter=Q(student__user=self.request.user, status="A"),
                ),
                has_pset_for_any_unit=Exists(
                    "group__unit__pset",
                    filter=Q(student__user=self.request.user, status="A"),
                ),
            )
        return queryset


class PublicCatalog(ListView[UnitGroup]):
    model = UnitGroup
    queryset = (
        UnitGroup.objects.filter(
            hidden=False,
        )
        .order_by("subject", "name")
        .annotate(num_psets=Count("unit__pset"))
    )

    template_name = "core/catalog_printable.html"


class UnitArtworkListView(ListView[UnitGroup]):
    model = UnitGroup
    queryset = (
        UnitGroup.objects.filter(hidden=False)
        .exclude(artist_name__exact="")
        .order_by("name")
    )
    template_name = "core/artwork_list.html"
    context_object_name = "unitgroups"

    def get_context_data(self, *args: Any, **kwargs: Any):
        context = super().get_context_data(*args, **kwargs)
        context["num_extra"] = (-self.queryset.count()) % 3  # type: ignore
        return context


def permitted(unit: Unit, request: HttpRequest, asking_solution: bool) -> bool:
    if getattr(request.user, "is_staff", False):
        return True
    elif isinstance(request.user, AnonymousUser):
        return False
    elif PSet.objects.filter(student__user=request.user, unit=unit).exists():
        return True
    elif UploadedFile.objects.filter(
        benefactor__semester__uses_legacy_pset_system=True,
        benefactor__user=request.user,
        category="psets",
        unit=unit,
    ).exists():
        return True
    elif (
        asking_solution is False
        and Student.objects.filter(user=request.user, unlocked_units=unit).exists()
    ):
        return True
    elif Student.objects.filter(
        user=request.user,
        unlocked_units=unit,
        semester__active=False,
    ).exists():
        return True
    elif Student.objects.filter(
        user=request.user,
        unlocked_units=unit,
        enabled=False,
    ).exists():
        return True
    return False


@login_required
def unit_problems(request: HttpRequest, pk: int) -> HttpResponse:
    unit = get_object_or_404(Unit, pk=pk)
    if permitted(unit, request, asking_solution=False):
        return get_from_google_storage(unit.problems_pdf_filename)
    else:
        raise PermissionDenied(f"Can't view the problems pdf for {unit}")


@login_required
def unit_tex(request: HttpRequest, pk: int) -> HttpResponse:
    unit = get_object_or_404(Unit, pk=pk)
    if permitted(unit, request, asking_solution=False):
        return get_from_google_storage(unit.problems_tex_filename)
    else:
        raise PermissionDenied(f"Can't view the problems TeX for {unit}")


@login_required
def unit_solutions(request: HttpRequest, pk: int) -> HttpResponse:
    unit = get_object_or_404(Unit, pk=pk)
    if permitted(unit, request, asking_solution=True):
        return get_from_google_storage(unit.solutions_pdf_filename)
    else:
        raise PermissionDenied(f"Can't view the solutions for {unit}")


class UserProfileUpdateView(
    LoginRequiredMixin,
    SuccessMessageMixin,
    UpdateView[UserProfile, BaseModelForm[UserProfile]],
):
    model = UserProfile
    fields = (
        "show_bars",
        "show_completed_by_default",
        "show_locked_by_default",
        "show_artwork_on_curriculum",
        "dynamic_progress",
        "use_twemoji",
        "unit_description",
    )
    success_url = reverse_lazy("profile")
    object: UserProfile

    def get_success_message(self, cleaned_data: dict[str, Any]) -> str:
        return f"Updated settings for {self.object.user.username}!"

    def get_object(self, queryset: Optional[QuerySet[Model]] = None) -> UserProfile:
        userprofile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return userprofile


@login_required
@require_POST
def dismiss(request: AuthHttpRequest) -> JsonResponse:
    profile = get_object_or_404(UserProfile, user=request.user)
    profile.last_notif_dismiss = timezone.now()
    profile.save()
    return JsonResponse({"result": "success"})
