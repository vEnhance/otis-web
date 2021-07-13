from django.core.files.storage import default_storage
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.utils.encoding import smart_str
from django.contrib.auth.decorators import login_required
from django.views.generic.list import ListView
from django.conf import settings
from hashlib import sha256
import os

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
	ext = filename[-3:]
	assert ext == 'tex' or ext == 'pdf'
	file = default_storage.open('units/' + h(filename) + '.' + ext)
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
