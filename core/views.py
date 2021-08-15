from dashboard.models import PSet, UploadedFile
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.views.generic.list import ListView
from roster.models import Student

from .models import Semester, Unit, UnitGroup
from .utils import get_from_google_storage

# Create your views here.

class UnitGroupListView(ListView):
	model = UnitGroup
	queryset = UnitGroup.objects.all().order_by('subject', 'name')\
			.prefetch_related('unit_set')

def permitted(unit: Unit, request: HttpRequest, asking_solution: bool) -> bool:
	if getattr(request.user, 'is_staff', False):
		return True
	elif isinstance(request.user, AnonymousUser):
		return False
	elif PSet.objects\
			.filter(student__user = request.user, unit = unit).exists():
		return True
	elif UploadedFile.objects\
			.filter(benefactor__semester__uses_legacy_pset_system = True,
					benefactor__user = request.user,
					category = 'psets',
					unit = unit).exists():
		return True
	elif asking_solution is False and Student.objects\
			.filter(user = request.user, unlocked_units = unit).exists():
		return True
	return False

@login_required
def unit_problems(request: HttpRequest, pk: int) -> HttpResponse:
	unit = Unit.objects.get(pk=pk)
	if permitted(unit, request, asking_solution = False):
		return get_from_google_storage(unit.problems_pdf_filename)
	else:
		raise PermissionDenied(f"Can't view the problems pdf for {unit}")

@login_required
def unit_tex(request: HttpRequest, pk: int) -> HttpResponse:
	unit = Unit.objects.get(pk=pk)
	if permitted(unit, request, asking_solution = False):
		return get_from_google_storage(unit.problems_tex_filename)
	else:
		raise PermissionDenied(f"Can't view the problems TeX for {unit}")

@login_required
def unit_solutions(request: HttpRequest, pk: int) -> HttpResponse:
	unit = Unit.objects.get(pk=pk)
	if permitted(unit, request, asking_solution = True):
		return get_from_google_storage(unit.solutions_pdf_filename)
	else:
		raise PermissionDenied(f"Can't view the solutions for {unit}")

@login_required
def classroom(request: HttpRequest):
	semester = Semester.objects.get(active=True)
	return HttpResponseRedirect(semester.classroom_url)
