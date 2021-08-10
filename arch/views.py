import logging
import traceback
from hashlib import sha256
from typing import Any, ClassVar, Dict

import reversion
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http import HttpRequest, HttpResponseRedirect, JsonResponse
from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from reversion.views import RevisionMixin
from roster.models import Student

from . import forms, models

ContextType = Dict[str, Any]

class ExistStudentRequiredMixin(LoginRequiredMixin):
	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
		if not request.user.is_authenticated:
			return super().dispatch(request, *args, **kwargs)
		assert isinstance(request.user, User)
		if not Student.objects.filter(user=request.user).exists() and not request.user.is_staff:
			raise PermissionDenied('You have to be enrolled in at least one semester '
					'of OTIS to use the ARCH system')
		else:
			return super().dispatch(request, *args, **kwargs)

class HintObjectView:
	kwargs: ClassVar[Dict] = {}
	def get_object(self, queryset: QuerySet[models.Hint] = None) -> models.Hint:
		if queryset is None:
			queryset = self.get_queryset() # type: ignore
		return get_object_or_404(queryset, problem__puid=self.kwargs['puid'],
				number=self.kwargs['number'])
class ProblemObjectView:
	kwargs: ClassVar[Dict] = {}
	def get_object(self, queryset: QuerySet[models.Problem] = None) -> models.Problem:
		if queryset is None:
			queryset = self.get_queryset() # type: ignore
		return get_object_or_404(queryset, puid=self.kwargs['puid'])

class HintList(ExistStudentRequiredMixin, ListView):
	context_object_name = "hint_list"
	def get_queryset(self):
		self.problem = get_object_or_404(models.Problem, **self.kwargs)
		return models.Hint.objects.filter(problem=self.problem).order_by('number')
	def get_context_data(self, **kwargs: Dict[Any, Any]):
		context = super().get_context_data(**kwargs)
		context['problem'] = self.problem
		return context

class HintDetail(HintObjectView, ExistStudentRequiredMixin, DetailView):
	context_object_name = "hint"
	model = models.Hint

class HintUpdate(HintObjectView, ExistStudentRequiredMixin, RevisionMixin, UpdateView):
	context_object_name = "hint"
	model = models.Hint
	form_class = forms.HintUpdateFormWithReason
	object: ClassVar[models.Hint] = models.Hint()
	def form_valid(self, form: BaseModelForm) -> HttpResponse:
		reversion.set_comment(form.cleaned_data['reason'] or form.cleaned_data['content'])
		return super().form_valid(form)
	def get_context_data(self, **kwargs: Any) -> ContextType:
		context = super().get_context_data(**kwargs)
		context['problem'] = self.object.problem
		return context
	def get_success_url(self):
		return self.object.get_absolute_url()

class ProblemUpdate(ProblemObjectView, ExistStudentRequiredMixin, RevisionMixin, UpdateView):
	context_object_name = "problem"
	model = models.Problem
	form_class = forms.ProblemUpdateFormWithReason
	object: ClassVar[models.Problem] = models.Problem()
	def form_valid(self, form: BaseModelForm) -> HttpResponse:
		reversion.set_comment(form.cleaned_data['reason'] or form.cleaned_data['description'])
		return super().form_valid(form)
	def get_success_url(self):
		return self.object.get_absolute_url()

class HintCreate(ExistStudentRequiredMixin, RevisionMixin, CreateView):
	context_object_name = "hint"
	fields = ('problem', 'number', 'keywords', 'content',)
	model = models.Hint
	def get_initial(self):
		initial = super(HintCreate, self).get_initial()
		initial = initial.copy()
		initial['problem'] = models.Problem.objects.get(puid=self.kwargs['puid'])
		return initial

class HintDelete(HintObjectView, ExistStudentRequiredMixin, RevisionMixin, DeleteView):
	context_object_name = "hint"
	model = models.Hint
	object: ClassVar[models.Hint] = models.Hint()
	def get_success_url(self):
		return reverse_lazy("hint-list", args=(self.object.problem.puid,))

class ProblemDelete(ProblemObjectView, ExistStudentRequiredMixin, RevisionMixin, DeleteView):
	context_object_name = "problem"
	model = models.Problem
	object: ClassVar[models.Problem] = models.Problem()
	def get_success_url(self):
		return reverse_lazy("arch-index")

# this is actually the index page as well :P bit of a hack I guess...
class ProblemCreate(ExistStudentRequiredMixin, RevisionMixin, CreateView):
	context_object_name = "problem"
	fields = ('puid', 'description',)
	model = models.Problem
	def get_context_data(self, **kwargs: Any):
		context = super().get_context_data(**kwargs)
		context['lookup_form'] = forms.ProblemSelectForm()
		context['num_problems'] = models.Problem.objects.all().count()
		context['num_hints'] = models.Hint.objects.all().count()
		context['lookup_url'] = reverse_lazy('arch-lookup',)
		return context

@login_required
def lookup(request: HttpRequest):
	if request.method == 'POST':
		form = forms.ProblemSelectForm(request.POST)
		assert form.is_valid()
		problem = form.cleaned_data['lookup_problem']
		return HttpResponseRedirect(problem.get_absolute_url())
	else:
		return HttpResponseRedirect(reverse_lazy('arch-index',))

@csrf_exempt
def archapi(request: HttpRequest) -> JsonResponse:
	if request.method != 'POST':
		return JsonResponse({'error': "☕"}, status = 418)
	if settings.PRODUCTION:
		token = request.POST.get('token')
		assert token is not None
		if not sha256(token.encode('ascii')).hexdigest() == settings.API_TARGET_HASH:
			return JsonResponse({'error': "☕"}, status = 418)

	def err(status: int = 400) -> JsonResponse:
		logging.error(traceback.format_exc())
		return JsonResponse(
				{'error': ''.join(traceback.format_exc(limit=1)) },
				status = status)

	action = request.POST['action']
	puid = request.POST['puid'].upper()

	if action == 'hints':
		problem = get_object_or_404(models.Problem, puid = puid)
		response = {
				'hints': [],
				'description': problem.description,
				'url': problem.get_absolute_url(),
				'add_url': reverse_lazy("hint-create",
					args = (problem.puid,))
				}
		for hint in models.Hint.objects.filter(problem=problem):
			response['hints'].append({
				'number': hint.number,
				'keywords': hint.keywords,
				'url': hint.get_absolute_url(),
				})
		return JsonResponse(response)

	if action == 'create':
		try:
			assert 'description' in request.POST
			problem = models.Problem(
					description = request.POST['description'],
					puid = puid
					)
			problem.save()
		except:
			return err()
		else:
			return JsonResponse({
				'edit_url': reverse_lazy('problem-update',
					args=(problem.puid,)),
				'view_url': problem.get_absolute_url(),
				})

	if action == 'add':
		problem = get_object_or_404(models.Problem, puid = puid)
		try:
			assert 'content' in request.POST
			assert 'keywords' in request.POST
			assert 'number' in request.POST
			hint = models.Hint(
					problem = problem,
					content = request.POST['content'],
					keywords = request.POST['keywords'],
					number = request.POST['number'],
					)
			hint.save()
		except AssertionError:
			return err()
		else:
			return JsonResponse({'url': hint.get_absolute_url()})

	return JsonResponse({})
