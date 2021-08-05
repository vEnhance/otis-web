import logging
from hashlib import sha256

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.http import (HttpRequest, HttpResponse, HttpResponseBadRequest,
                         HttpResponseRedirect, HttpResponseServerError)
from django.views.generic.list import ListView

logger = logging.getLogger(__name__)

import dashboard.models
import roster.models

from .models import Semester, Unit, UnitGroup


def h(value):
	s = settings.UNIT_HASH_KEY + '|' + value
	return sha256(s.encode('ascii')).hexdigest()

# Create your views here.

class UnitGroupListView(ListView):
	model = UnitGroup
	queryset = UnitGroup.objects.all().order_by('subject', 'name')\
			.prefetch_related('unit_set')

def _get_from_google_storage(filename : str):
	ext = filename[-4:]
	if not (ext == '.tex' or ext == '.pdf'):
		return HttpResponseBadRequest('Bad filename extension')
	try:
		file = default_storage.open('units/' + h(filename) + ext)
	except FileNotFoundError:
		errmsg = f"Unable to find {filename}."
		logger.critical(errmsg)
		return HttpResponseServerError(errmsg)
	response = HttpResponse(content = file)
	response['Content-Type'] = f'application/{ext}'
	response['Content-Disposition'] = f'attachment; filename="{filename}"'
	return response

def permitted(unit : Unit, request : HttpRequest, asking_solution : bool) -> bool:
	if getattr(request.user, 'is_staff', False):
		return True
	elif dashboard.models.PSet.objects\
			.filter(student__user = request.user, unit = unit).exists():
		return True
	elif dashboard.models.UploadedFile.objects\
			.filter(benefactor__semester__uses_legacy_pset_system = True,
					benefactor__user = request.user,
					category = 'psets',
					unit = unit).exists():
		return True
	elif asking_solution is False and roster.models.Student.objects\
			.filter(user = request.user, unlocked_units = unit).exists():
		return True
	return False

@login_required
def unit_problems(request, pk) -> HttpResponse:
	unit = Unit.objects.get(pk=pk)
	if permitted(unit, request, asking_solution = False):
		return _get_from_google_storage(unit.problems_pdf_filename)
	else:
		raise PermissionDenied(f"Can't view the problems pdf for {unit}")

@login_required
def unit_tex(request, pk) -> HttpResponse:
	unit = Unit.objects.get(pk=pk)
	if permitted(unit, request, asking_solution = False):
		return _get_from_google_storage(unit.problems_tex_filename)
	else:
		raise PermissionDenied(f"Can't view the problems TeX for {unit}")

@login_required
def unit_solutions(request, pk) -> HttpResponse:
	unit = Unit.objects.get(pk=pk)
	if permitted(unit, request, asking_solution = True):
		return _get_from_google_storage(unit.solutions_pdf_filename)
	else:
		raise PermissionDenied(f"Can't view the solutions for {unit}")

@login_required
def classroom(request):
	semester = Semester.objects.get(active=True)
	return HttpResponseRedirect(semester.classroom_url)
