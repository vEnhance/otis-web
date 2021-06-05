from django.shortcuts import redirect
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.utils.encoding import smart_str
from django.contrib.auth.decorators import login_required
from django.views.generic.list import ListView
from hashlib import sha256
import os
import pathlib


from .models import UnitGroup, Unit, Semester

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
def unit_tex(request, pk, hash):
	unit = Unit.objects.get(pk=pk)
	url = unit.prob_url
	if sha(url.encode('utf-8')) == hash:
		tex_dir = pathlib.Path(os.getenv(
			"PROBLEM_TEX_PATH",
			'/home/evan/Documents/OTIS/TeX/'))
		# kludge
		basename = url[url.rindex('/')+1:url.index('?')].replace('.pdf', '.tex')
		tex_path = tex_dir / (basename[:3] + '-tex-' + basename[4:])
		with open(tex_path, 'r') as f:
			content = ''.join(f.readlines())
		response = HttpResponse(content, content_type='application/tex')
		response['Content-Disposition']='attachment; filename=' \
				 + smart_str(basename)
		return response
	else:
		return HttpResponseBadRequest("400. Wrong hash.")

@login_required
def unit_solutions(request, pk, hash):
	unit = Unit.objects.get(pk=pk)
	return _core_redir(unit.soln_url, hash)

@login_required
def classroom(request):
	semester = Semester.objects.get(active=True)
	return HttpResponseRedirect(semester.classroom_url)
