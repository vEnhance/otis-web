from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from hashlib import sha256
from django.contrib.auth.decorators import login_required

from django.views.generic.list import ListView
from .models import UnitGroup, Unit, Semester

from hashlib import sha256
def sha(value):
	return sha256(value).hexdigest()

# Create your views here.

class UnitGroupListView(ListView):
	model = UnitGroup
	queryset = UnitGroup.objects.all().order_by('subject', 'name')\
			.prefetch_related('unit_set')

def _core_redir(url, hash):
	if sha(url.encode('utf-8')) == hash:
		# return HttpResponse(url)
		return redirect(url, permanent=False)
	else:
		return HttpResponseBadRequest("400. Wrong hash.")

@login_required
def unit_problems(request, pk, hash):
	unit = Unit.objects.get(pk=pk)
	return _core_redir(unit.prob_url, hash)

@login_required
def unit_solutions(request, pk, hash):
	unit = Unit.objects.get(pk=pk)
	return _core_redir(unit.soln_url, hash)

@login_required
def classroom(request):
	semester = Semester.objects.get(active=True)
	return HttpResponseRedirect(semester.classroom_url)
