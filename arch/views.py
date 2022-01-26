from typing import Any, ClassVar, Dict

import reversion
from core.utils import storage_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http import Http404, HttpRequest, HttpResponseRedirect
from django.http.response import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from reversion.views import RevisionMixin
from roster.models import Student

from arch.forms import ProblemSelectForm

from .forms import HintUpdateFormWithReason
from .models import Hint, Problem

ContextType = Dict[str, Any]


class ExistStudentRequiredMixin(LoginRequiredMixin):
	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
		if not request.user.is_authenticated:
			return super().dispatch(request, *args, **kwargs)
		assert isinstance(request.user, User)
		if not Student.objects.filter(user=request.user).exists() and not request.user.is_staff:
			raise PermissionDenied(
				'You have to be enrolled in at least one semester '
				'of OTIS to use the ARCH system'
			)
		else:
			return super().dispatch(request, *args, **kwargs)


class HintObjectView:
	kwargs: ClassVar[Dict[str, Any]] = {}

	def get_object(self, queryset: QuerySet[Hint] = None) -> Hint:
		if queryset is None:
			queryset = self.get_queryset()  # type: ignore
		assert queryset is not None
		return get_object_or_404(
			queryset, problem__puid=self.kwargs['puid'], number=self.kwargs['number']
		)


class ProblemObjectView:
	kwargs: ClassVar[Dict[str, Any]] = {}

	def get_object(self, queryset: QuerySet[Problem] = None) -> Problem:
		if queryset is None:
			queryset = self.get_queryset()  # type: ignore
		assert queryset is not None
		return get_object_or_404(queryset, puid=self.kwargs['puid'])


class HintList(ExistStudentRequiredMixin, ListView[Hint]):
	context_object_name = "hint_list"

	def get_queryset(self):
		self.problem = get_object_or_404(Problem, **self.kwargs)
		return Hint.objects.filter(problem=self.problem).order_by('number')

	def get_context_data(self, **kwargs: Dict[Any, Any]):
		context = super().get_context_data(**kwargs)
		context['problem'] = self.problem
		context['statement'] = self.problem.get_statement
		return context


class HintDetail(HintObjectView, ExistStudentRequiredMixin, DetailView[Hint]):
	context_object_name = "hint"
	model = Hint


class HintDetailByPK(ExistStudentRequiredMixin, DetailView[Hint]):
	context_object_name = "hint"
	model = Hint


class HintUpdate(
	HintObjectView, ExistStudentRequiredMixin, RevisionMixin,
	UpdateView[Hint, HintUpdateFormWithReason]
):
	context_object_name = "hint"
	model = Hint
	form_class = HintUpdateFormWithReason
	object: ClassVar[Hint] = Hint()

	def form_valid(self, form: HintUpdateFormWithReason) -> HttpResponse:
		reversion.set_comment(form.cleaned_data['reason'] or form.cleaned_data['content'])
		return super().form_valid(form)

	def get_context_data(self, **kwargs: Any) -> ContextType:
		context = super().get_context_data(**kwargs)
		context['problem'] = self.object.problem
		return context

	def get_success_url(self):
		return self.object.get_absolute_url()


class HintUpdateByPK(
	ExistStudentRequiredMixin, RevisionMixin, UpdateView[Hint, HintUpdateFormWithReason]
):
	context_object_name = "hint"
	model = Hint
	form_class = HintUpdateFormWithReason
	object: ClassVar[Hint] = Hint()

	def form_valid(self, form: HintUpdateFormWithReason) -> HttpResponse:
		reversion.set_comment(form.cleaned_data['reason'] or form.cleaned_data['content'])
		return super().form_valid(form)

	def get_context_data(self, **kwargs: Any) -> ContextType:
		context = super().get_context_data(**kwargs)
		context['problem'] = self.object.problem
		return context

	def get_success_url(self):
		return self.object.get_absolute_url()


class ProblemUpdate(
	ProblemObjectView, ExistStudentRequiredMixin, RevisionMixin,
	UpdateView[Problem, BaseModelForm[Problem]]
):
	context_object_name = "problem"
	model = Problem
	fields = ('puid', )

	def get_context_data(self, **kwargs: Any):
		context = super().get_context_data(**kwargs)
		context['num_problems'] = Problem.objects.all().count()
		context['num_hints'] = Hint.objects.all().count()
		return context

	def get_success_url(self) -> str:
		return self.object.get_absolute_url()  # type: ignore


class HintCreate(
	ExistStudentRequiredMixin, RevisionMixin, CreateView[Hint, BaseModelForm[Hint]]
):
	context_object_name = "hint"
	fields = (
		'problem',
		'number',
		'keywords',
		'content',
	)
	model = Hint

	def get_initial(self):
		initial = super(HintCreate, self).get_initial()
		initial = initial.copy()
		initial['problem'] = Problem.objects.get(puid=self.kwargs['puid'])
		return initial


class HintDelete(HintObjectView, ExistStudentRequiredMixin, RevisionMixin, DeleteView):
	context_object_name = "hint"
	model = Hint
	object: ClassVar[Hint] = Hint()

	def get_success_url(self):
		return reverse_lazy("hint-list", args=(self.object.problem.puid, ))


class ProblemDelete(ProblemObjectView, ExistStudentRequiredMixin, RevisionMixin, DeleteView):
	context_object_name = "problem"
	model = Problem
	object: ClassVar[Problem] = Problem()

	def get_success_url(self):
		return reverse_lazy("arch-index")


# this is actually the index page as well :P bit of a hack I guess...
class ProblemCreate(
	ExistStudentRequiredMixin, RevisionMixin, CreateView[Problem, BaseModelForm[Problem]]
):
	context_object_name = "problem"
	fields = ('puid', )
	model = Problem
	template_name = 'arch/index.html'

	def get_context_data(self, **kwargs: Any):
		context = super().get_context_data(**kwargs)
		context['lookup_form'] = ProblemSelectForm()
		context['num_problems'] = Problem.objects.all().count()
		context['num_hints'] = Hint.objects.all().count()
		context['lookup_url'] = reverse_lazy('arch-lookup', )
		return context


@login_required
def lookup(request: HttpRequest):
	if request.method == 'POST':
		form = ProblemSelectForm(request.POST)
		assert form.is_valid()
		problem = form.cleaned_data['problem']
		return HttpResponseRedirect(problem.get_absolute_url())
	else:
		return HttpResponseRedirect(reverse_lazy('arch-index', ))


@login_required
def view_solution(request: HttpRequest, puid: str):
	solution_target_name = 'pdfs/' + storage_hash(puid) + '.tex'
	if default_storage.exists(solution_target_name):
		solution_url = default_storage.url(solution_target_name)
		return HttpResponseRedirect(solution_url)
	else:
		raise Http404
