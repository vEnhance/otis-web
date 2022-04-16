from typing import Any, Dict

from braces.views import LoginRequiredMixin
from dashboard.models import PSet, UploadedFile
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.db.models.base import Model
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http import HttpRequest, HttpResponse
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls.base import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic.edit import UpdateView
from django.views.generic.list import ListView
from otisweb.utils import AuthHttpRequest
from roster.models import Student

from core.models import UserProfile

from .models import Unit, UnitGroup
from .utils import get_from_google_storage

# Create your views here.


class UnitGroupListView(ListView[UnitGroup]):
	model = UnitGroup
	queryset = UnitGroup.objects.filter(
		hidden=False,
	).order_by('subject', 'name').prefetch_related('unit_set')


def permitted(unit: Unit, request: HttpRequest, asking_solution: bool) -> bool:
	if getattr(request.user, 'is_staff', False):
		return True
	elif isinstance(request.user, AnonymousUser):
		return False
	elif PSet.objects.filter(student__user=request.user, unit=unit).exists():
		return True
	elif UploadedFile.objects.filter(
		benefactor__semester__uses_legacy_pset_system=True,
		benefactor__user=request.user,
		category='psets',
		unit=unit
	).exists():
		return True
	elif asking_solution is False and Student.objects.filter(
		user=request.user, unlocked_units=unit
	).exists():
		return True
	elif Student.objects.filter(
		user=request.user,
		unlocked_units=unit,
		semester__active=False,
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
	LoginRequiredMixin, SuccessMessageMixin, UpdateView[UserProfile, BaseModelForm[UserProfile]]
):
	model = UserProfile
	fields = ('show_bars', 'show_completed_by_default', 'show_locked_by_default')
	success_url = reverse_lazy("profile")
	object: UserProfile

	def get_success_message(self, cleaned_data: Dict[str, Any]) -> str:
		return f"Updated settings for {self.object.user.username}!"

	def get_object(self, queryset: QuerySet[Model] = None) -> UserProfile:
		userprofile, _ = UserProfile.objects.get_or_create(user=self.request.user)
		return userprofile


@login_required
@require_POST
def dismiss_emails(request: AuthHttpRequest) -> JsonResponse:
	profile = UserProfile.objects.get(user=request.user)
	profile.last_email_dismiss = timezone.now()
	profile.save()
	return JsonResponse({'result': 'success'})


@login_required
@require_POST
def dismiss_downloads(request: AuthHttpRequest) -> JsonResponse:
	profile = UserProfile.objects.get(user=request.user)
	profile.last_download_dismiss = timezone.now()
	profile.save()
	return JsonResponse({'result': 'success'})
