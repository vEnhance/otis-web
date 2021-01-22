from django.shortcuts import render
from django.views.generic import ListView
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

class ListProblems(ListView):
	def get_queryset(self):
		group = core.models.UnitGroup.objects.get(id=self.kwargs['group'])
		return models.Problem.objects.filter(group=group)\
				.order_by(problem_source, description)

class ListHints(ListView):
	def get_queryset(self):
		problem  = models.Problem.objects.get(id=self.kwargs['problem'])
		sq = models.Hint.objects.filter(number=OuterRef('number'))\
				.order_by('-created_at').values('id')[:1]
		return models.Hint.objects.filter(problem=problem).filter(id=Subquery(sq))

class UpdateHint(RevisionMixin, UpdateView):
	model = models.Hint
	form_class = forms.HintFormWithReason
	def get_success_url(self):
		return reverse_lazy("list_hints", args=(self.object.problem.id,))
	def form_valid(self, form):
		reversion.set_comment(form.cleaned_data['reason'] or form.cleaned_data['content'])
		return super(UpdateHint, self).form_valid(form)

class UpdateProblem(RevisionMixin, UpdateView):
	model = models.Problem
	form_class = forms.ProblemFormWithReason
	def get_success_url(self):
		return reverse_lazy("list_problems", args=(self.object.group.id,))
	def form_valid(self, form):
		reversion.set_comment(form.cleaned_data['reason'] or form.cleaned_data['content'])
		return super(UpdateHint, self).form_valid(form)

class CreateHint(RevisionMixin, CreateView):
	fields = ('keywords', 'number', 'content',)
	model = models.Hint
class CreateProblem(RevisionMixin, CreateView):
	fields = ('source', 'description',)
	model = models.Problem

class DeleteHint(RevisionMixin, DeleteView):
	model = models.Hint
class DeleteProblem(RevisionMixin, DeleteView):
	model = models.Problem
