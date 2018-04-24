from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseBadRequest
from hashlib import sha256
from django.contrib.auth.decorators import login_required

from django.views.generic.list import ListView
from .models import UnitGroup, Unit

from hashlib import sha256
def sha(value):
	return sha256(value).hexdigest()

# Create your views here.

class UnitGroupListView(ListView):
	model = UnitGroup
	queryset = UnitGroup.objects.all().order_by('subject', 'name')\
			.prefetch_related('unit_set')

def _core_redir(url, hash):
	if sha(url) == hash:
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
