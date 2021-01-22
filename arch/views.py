from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.db.models import Subquery, OuterRef
from django.urls import reverse_lazy
from django import forms
from reversion.views import RevisionMixin
import reversion

from . import models
from . import forms
import core

# Create your views here.

class ProblemList(LoginRequiredMixin, ListView):
	context_object_name = "problem_list"
	def get_queryset(self):
		group = core.models.UnitGroup.objects.get(id=self.kwargs['group'])
		return models.Problem.objects.filter(group=group)
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['group'] = core.models.UnitGroup.objects.get(id=self.kwargs['group'])
		return context

class HintList(LoginRequiredMixin, ListView):
	context_object_name = "hint_list"
	def get_queryset(self):
		self.problem = models.Problem.objects.get(id=self.kwargs['problem'])
		return models.Hint.objects.filter(problem=self.problem)
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['problem'] = self.problem
		return context
class HintDetail(LoginRequiredMixin, DetailView):
	context_object_name = "hint"
	model = models.Hint

class HintUpdate(LoginRequiredMixin, RevisionMixin, UpdateView):
	context_object_name = "hint"
	model = models.Hint
	form_class = forms.HintUpdateFormWithReason
	def form_valid(self, form):
		reversion.set_comment(form.cleaned_data['reason'] or form.cleaned_data['content'])
		return super().form_valid(form)
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['problem'] = self.object.problem
		return context
class ProblemUpdate(LoginRequiredMixin, RevisionMixin, UpdateView):
	context_object_name = "problem"
	model = models.Problem
	form_class = forms.ProblemUpdateFormWithReason
	def get_success_url(self):
		return reverse_lazy("hint_list", args=(self.object.id,))
	def form_valid(self, form):
		reversion.set_comment(form.cleaned_data['reason'] or form.cleaned_data['description'])
		return super().form_valid(form)
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['group'] = self.object.group
		return context

class HintCreate(LoginRequiredMixin, RevisionMixin, CreateView):
	context_object_name = "hint"
	fields = ('problem', 'keywords', 'number', 'content',)
	model = models.Hint
	def get_initial(self):
		initial = super(HintCreate, self).get_initial()
		initial = initial.copy()
		initial['problem'] = self.kwargs['problem']
		return initial
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['problem'] = models.Problem.objects.get(id=self.kwargs['problem'])
		return context
class ProblemCreate(LoginRequiredMixin, RevisionMixin, CreateView):
	context_object_name = "problem"
	fields = ('group', 'source', 'description',)
	model = models.Problem
	def get_initial(self):
		initial = super(ProblemCreate, self).get_initial()
		initial = initial.copy()
		initial['group'] = self.kwargs['group']
		return initial
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['group'] = core.models.UnitGroup.objects.get(id=self.kwargs['group'])
		return context

class HintDelete(LoginRequiredMixin, RevisionMixin, DeleteView):
	context_object_name = "hint"
	model = models.Hint
	def get_success_url(self):
		return reverse_lazy("hint_list", args=(self.object.problem.id,))

