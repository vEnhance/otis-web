from django.core.files.storage import default_storage
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.views.generic.list import ListView
from django.conf import settings
from hashlib import sha256
import logging
logger = logging.getLogger(__name__)

from .models import UnitGroup, Unit, Semester

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

@login_required
def unit_problems(request, pk):
	unit = Unit.objects.get(pk=pk)
	return _get_from_google_storage(unit.problems_pdf_filename)

@login_required
def unit_tex(request, pk):
	unit = Unit.objects.get(pk=pk)
	return _get_from_google_storage(unit.problems_tex_filename)

@login_required
def unit_solutions(request, pk):
	unit = Unit.objects.get(pk=pk)
	return _get_from_google_storage(unit.solutions_pdf_filename)

@login_required
def classroom(request):
	semester = Semester.objects.get(active=True)
	return HttpResponseRedirect(semester.classroom_url)
