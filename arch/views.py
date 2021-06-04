from typing import ClassVar, Dict
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from reversion.views import RevisionMixin
from typing import ClassVar
from hashlib import sha256
from django.views.decorators.csrf import csrf_exempt
import reversion
import traceback
import logging

from . import models
from . import forms

class HintObjectView:
	kwargs : ClassVar[Dict] = {}
	def get_object(self, queryset=None):
		if queryset is None:
			queryset = self.get_queryset() # type: ignore
		return queryset.get(problem__puid=self.kwargs['puid'],
				number=self.kwargs['number'])
class ProblemObjectView:
	kwargs : ClassVar[Dict] = {}
	def get_object(self, queryset=None):
		if queryset is None:
			queryset = self.get_queryset() # type: ignore
		return queryset.get(puid=self.kwargs['puid'])

class HintList(LoginRequiredMixin, ListView):
	context_object_name = "hint_list"
	def get_queryset(self):
		self.problem = models.Problem.objects.get(**self.kwargs)
		return models.Hint.objects.filter(problem=self.problem).order_by('number')
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['problem'] = self.problem
		return context

class HintDetail(HintObjectView, LoginRequiredMixin, DetailView):
	context_object_name = "hint"
	model = models.Hint

class HintUpdate(HintObjectView, LoginRequiredMixin, RevisionMixin, UpdateView):
	context_object_name = "hint"
	model = models.Hint
	form_class = forms.HintUpdateFormWithReason
	object : ClassVar[models.Hint] = models.Hint()
	def form_valid(self, form):
		reversion.set_comment(form.cleaned_data['reason'] or form.cleaned_data['content'])
		return super().form_valid(form)
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['problem'] = self.object.problem
		return context
	def get_success_url(self):
		return self.object.get_absolute_url()

class ProblemUpdate(ProblemObjectView, LoginRequiredMixin, RevisionMixin, UpdateView):
	context_object_name = "problem"
	model = models.Problem
	form_class = forms.ProblemUpdateFormWithReason
	object : ClassVar[models.Problem] = models.Problem()
	def form_valid(self, form):
		reversion.set_comment(form.cleaned_data['reason'] or form.cleaned_data['description'])
		return super().form_valid(form)
	def get_success_url(self):
		return self.object.get_absolute_url()

class HintCreate(LoginRequiredMixin, RevisionMixin, CreateView):
	context_object_name = "hint"
	fields = ('problem', 'number', 'keywords', 'content',)
	model = models.Hint
	def get_initial(self):
		initial = super(HintCreate, self).get_initial()
		initial = initial.copy()
		initial['problem'] = models.Problem.objects.get(puid=self.kwargs['puid'])
		return initial

class HintDelete(HintObjectView, LoginRequiredMixin, RevisionMixin, DeleteView):
	context_object_name = "hint"
	model = models.Hint
	object : ClassVar[models.Hint] = models.Hint()
	def get_success_url(self):
		return reverse_lazy("hint-list", args=(self.object.problem.puid,))

class ProblemDelete(ProblemObjectView, LoginRequiredMixin, RevisionMixin, DeleteView):
	context_object_name = "problem"
	model = models.Problem
	object : ClassVar[models.Problem] = models.Problem()
	def get_success_url(self):
		return reverse_lazy("arch-index")

# this is actually the index page as well :P bit of a hack I guess...
class ProblemCreate(LoginRequiredMixin, RevisionMixin, CreateView):
	context_object_name = "problem"
	fields = ('puid', 'description',)
	model = models.Problem
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['lookup_form'] = forms.ProblemSelectForm()
		context['num_problems'] = models.Problem.objects.all().count()
		context['num_hints'] = models.Hint.objects.all().count()
		context['lookup_url'] = reverse_lazy('arch-lookup',)
		return context

@login_required
def lookup(request):
	if request.method == 'POST':
		form = forms.ProblemSelectForm(request.POST)
		assert form.is_valid()
		problem = form.cleaned_data['lookup_problem']
		return HttpResponseRedirect(problem.get_absolute_url())
	else:
		return HttpResponseRedirect(reverse_lazy('arch-index',))

TARGET_HASH = '1c3592aa9241522fea1dd572c43c192a277e832dcd1ae63adfe069cb05624ead'
# what don't look at me like that
# who is bored enough to try hacking the arch api

@csrf_exempt
def api(request):
	if request.method != 'POST':
		return HttpResponse("☕", status = 418)
	token = request.POST.get('token')
	if not sha256(token.encode('ascii')).hexdigest() == TARGET_HASH:
		return HttpResponse("☕", status = 418)

	def err() -> JsonResponse:
		logging.error(traceback.format_exc())
		return JsonResponse(
				{'error' : ''.join(traceback.format_exc(limit=1)) },
				status = 400)

	action = request.POST.get('action')
	puid = request.POST.get('puid').upper()

	if action == 'hints':
		try:
			problem = models.Problem.objects.get(puid = puid)
		except:
			return err()
		response = {
				'hints' : [],
				'url' : problem.get_absolute_url()
				}
		for hint in models.Hint.objects.filter(problem=problem):
			response['hints'].append({
				'number' : hint.number,
				'keywords' : hint.keywords
				})
		return JsonResponse(response)

	if action == 'create':
		try:
			problem = models.Problem(
					description = request.POST.get('description'),
					puid = puid
					)
			problem.save()
		except:
			return err()
		else:
			return JsonResponse({
				'edit_link' : reverse_lazy('problem-update', (problem.puid,)),
				'view_link' : problem.get_absolute_url(),
				})

	if action == 'add':
		try:
			problem = models.Problem.objects.get(puid = puid)
			hint = models.Hint(
					problem = problem,
					content = request.POST.get('content'),
					keywords = request.POST.get('keywords'),
					number = request.POST.get('number'),
					)
			hint.save()
		except:
			return err()
		else:
			return JsonResponse({'link' : hint.get_absolute_url()})
