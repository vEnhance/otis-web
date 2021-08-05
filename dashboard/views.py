# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from datetime import timedelta
from typing import Any, Dict, Optional

import core.models
import exams.models
import roster.models
import roster.utils
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, OuterRef, Q, Subquery, Sum
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect  # NOQA
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils.timezone import now
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView

import dashboard.models

from . import forms


class Meter:
	def __init__(self,
			name : str,
			emoji : str,
			value : int,
			unit : str,
			color: str
			):
		self.name = name
		self.emoji = emoji
		self.value = value
		self.unit = unit
		self.color = color

	@property
	def level(self) -> int:
		return int(self.value**0.5)
	@property
	def excess(self) -> int:
		return self.value - self.level ** 2
	@property
	def bar_max(self) -> int:
		return self.level * 2 + 1
	@property
	def percent(self) -> int:
		return 15 + int(85 * (self.excess+0.2) / (self.bar_max+0.2))
	@property
	def needed(self) -> int:
		return (self.level+1) ** 2 - self.value
	@property
	def thresh(self) -> int:
		return (self.level+1) ** 2
	@property
	def total(self):
		return self.value

	@staticmethod
	def ClubMeter(value: int):
		return Meter(name = "Dexterity", emoji = "♣️", value = value,
				unit = "♣", color = '#007bff;')
	@staticmethod
	def HeartMeter(value: int):
		return Meter(name = "Wisdom", emoji = "🕰️", value = value,
				unit = "♥", color = '#198754')
	@staticmethod
	def SpadeMeter(value: int):
		return Meter(name = "Strength", emoji = "🏆", value = value,
				unit = "♠", color = '#ae610f')
	@staticmethod
	def DiamondMeter(value: int):
		return Meter(name = "Charisma", emoji = "㊙️", value = value,
				unit = "◆", color = '#9c1421')

def _get_meter_update(student: roster.models.Student):
	psets = dashboard.models.PSet.objects\
			.filter(student = student, approved = True, eligible = True)
	pset_data = psets.aggregate(Sum('clubs'), Sum('hours'))
	total_diamonds = student.achievements.aggregate(Sum('diamonds'))['diamonds__sum'] or 0
	quiz_data = exams.models.ExamAttempt.objects.filter(student = student)
	total_spades = \
			(quiz_data.aggregate(Sum('score'))['score__sum'] or 0) \
			+ (student.usemo_score or 0)
	meters = {
		'clubs' : Meter.ClubMeter(pset_data['clubs__sum'] or 0),
		'hearts' : Meter.HeartMeter(int(pset_data['hours__sum'] or 0)),
		'diamonds' : Meter.DiamondMeter(total_diamonds),
		'spades' : Meter.SpadeMeter(total_spades), # TODO input value
		}
	level_number = sum(meter.level for meter in meters.values())
	level = dashboard.models.Level.objects\
			.filter(threshold__lte = level_number).order_by('threshold').first()
	level_name = level.name if level is not None else 'Initiate'
	return {
			'psets' : psets,
			'pset_data' : pset_data,
			'quiz_data' : quiz_data,
			'meters' : meters,
			'level_number' : level_number,
			'level_name' : level_name
			}

@login_required
def portal(request, student_id) -> HttpResponse:
	student = roster.utils.get_student(student_id)
	roster.utils.check_can_view(request, student, delinquent_check = False)
	if roster.utils.is_delinquent_locked(request, student):
		return HttpResponseRedirect(reverse_lazy('invoice', args=(student_id,)))
	semester = student.semester

	# check if the student has any new processed suggestions
	suggestions = dashboard.models.ProblemSuggestion.objects.filter(
			resolved = True, student = student, notified = False)

	context : Dict[str, Any] = {}
	context['title'] = f"{student.name} ({semester.name})"
	context['student'] = student
	context['semester'] = semester
	context['suggestions'] = list(suggestions)
	context['omniscient'] = student.is_taught_by(request.user)
	context['curriculum'] = student.generate_curriculum_rows(
			omniscient = context['omniscient'])
	context['tests'] = exams.models.PracticeExam.objects.filter(
			is_test = True, family = semester.exam_family, due_date__isnull=False)
	context['quizzes'] = exams.models.PracticeExam.objects.filter(
			is_test = False, family = semester.exam_family, due_date__isnull=False)
	context['num_sem_download'] = dashboard.models.SemesterDownloadFile\
			.objects.filter(semester = semester).count()
	context.update(_get_meter_update(student))
	return render(request, "dashboard/portal.html", context)

@login_required
def achievements(request, student_id) -> HttpResponse:
	student = roster.utils.get_student(student_id)
	roster.utils.check_can_view(request, student)
	context : Dict[str,Any] = {
			'student' : student,
			'form' : forms.DiamondsForm(),
			'achievements' : student.achievements.all().order_by('name'),
			}
	if request.method == 'POST':
		form = forms.DiamondsForm(request.POST)
		if form.is_valid():
			code = form.cleaned_data['code']
			if student.achievements.filter(code__iexact = code).exists():
				messages.warning(request, "You already earned this achievement!")
			else:
				achievement : dashboard.models.Achievement \
						= get_object_or_404(dashboard.models.Achievement, code__iexact = code)
				student.achievements.add(achievement)
				context['obtained_achievement']  = achievement
			form = forms.DiamondsForm()
	else:
		form = forms.DiamondsForm()
	try:
		context['first_achievement'] = dashboard.models.Achievement.objects.get(pk=1)
	except dashboard.models.Achievement.DoesNotExist:
		pass
	context.update(_get_meter_update(student))
	return render(request, "dashboard/achievements.html", context)

@login_required
def submit_pset(request, student_id) -> HttpResponse:
	student = roster.utils.get_student(student_id)
	roster.utils.check_can_view(request, student)
	if request.method == 'POST':
		form = forms.PSetForm(request.POST, request.FILES)
	else:
		form = forms.PSetForm()

	available = student.generate_curriculum_queryset().filter(has_pset = False)
	form.fields['next_unit_to_unlock'].queryset = available
	form.fields['unit'].queryset = available
	if request.method == 'POST' and form.is_valid():
		pset = form.save(commit=False)
		if dashboard.models.PSet.objects.filter(
				student = student,
				unit = pset.unit).exists():
			messages.error(request,
					"You have already submitted for this unit.")
		else:
			f = dashboard.models.UploadedFile(
					benefactor = student,
					owner = student.user,
					category = 'psets',
					description = '',
					content = form.cleaned_data['content'],
					unit = pset.unit,
					)
			f.save()
			pset.student = student
			pset.upload = f
			pset.save()
			messages.success(request,
					"The problem set is submitted successfully "
					"and is pending review!")

	# TODO more stats
	context = {
			'title' : 'Ready to submit?',
			'student' : student,
			'pending_psets' : \
					dashboard.models.PSet.objects\
					.filter(student = student, approved = False)\
					.order_by('-upload__created_at'),
			'approved_psets' : \
					dashboard.models.PSet.objects\
					.filter(student = student, approved = True)\
					.order_by('-upload__created_at'),
			'form' : form,
			}
	return render(request, "dashboard/submit_pset_form.html", context)

@login_required
def uploads(request, student_id, unit_id) -> HttpResponse:
	student = roster.utils.get_student(student_id)
	roster.utils.check_can_view(request, student)
	if unit_id != "0":
		unit : Optional[core.models.Unit] = get_object_or_404(core.models.Unit.objects, id = unit_id)
	else:
		unit = None
	uploads = dashboard.models.UploadedFile.objects.filter(benefactor=student, unit=unit)
	if unit is not None \
			and not student.check_unit_unlocked(unit) \
			and not uploads.exists():
		raise PermissionDenied("This unit is not unlocked yet")

	form = None
	if request.method == "POST":
		form = forms.NewUploadForm(request.POST, request.FILES)
		if form.is_valid():
			new_upload = form.save(commit=False)
			new_upload.unit = unit
			new_upload.benefactor = student
			new_upload.owner = request.user
			new_upload.save()
			messages.success(request, "New file has been uploaded.")
			form = None # clear form on successful upload, prevent duplicates
	if form is None:
		form = forms.NewUploadForm(initial = {'unit' : unit})

	context : Dict[str, Any] = {}
	context['title'] = 'File Uploads'
	context['student'] = student
	context['unit'] = unit
	context['form'] = form
	context['files'] = uploads
	# TODO form for adding new files
	return render(request, "dashboard/uploads.html", context)

@login_required
def index(request) -> HttpResponse:
	students = roster.utils.get_visible_students(
			request.user, current=True)
	if len(students) == 1: # unique match
		return HttpResponseRedirect(\
				reverse("portal", args=(students[0].id,)))

	context : Dict[str, Any] = {}
	context['title'] = "Current Semester Listing"
	context['students'] = students
	context['stulist_show_semester'] = False
	context['submitted_registration'] = roster.models.StudentRegistration.objects\
			.filter(user = request.user, container__semester__active = True)\
			.exists()

	return render(request, "dashboard/stulist.html", context)

@login_required
def past(request, semester = None):
	students = roster.utils.get_visible_students(
			request.user, current=False)
	if semester is None:
		students = students.order_by('-semester',
				'user__first_name', 'user__last_name')[0:256]
	else:
		students = students.filter(semester=semester)
	context = {}
	context['title'] = "Previous Semester Listing"
	context['students'] = students
	context['stulist_show_semester'] = True
	return render(request, "dashboard/stulist.html", context)

class UpdateFile(LoginRequiredMixin, UpdateView):
	model = dashboard.models.UploadedFile
	fields = ('category', 'content', 'description',)
	object : dashboard.models.UploadedFile

	def get_success_url(self):
		stu_id = self.object.benefactor.id
		unit_id = self.object.unit.id if self.object.unit is not None else 0
		return reverse("uploads", args=(stu_id, unit_id,))

	def get_object(self, *args, **kwargs):
		obj = super(UpdateFile, self).get_object(*args, **kwargs)
		assert isinstance(obj, dashboard.models.UploadedFile)
		if not obj.owner == self.request.user \
				and getattr(self.request.user, 'is_staff', False):
			raise PermissionDenied("Not authorized to update this file")
		return obj

class DeleteFile(LoginRequiredMixin, DeleteView):
	model = dashboard.models.UploadedFile
	success_url = reverse_lazy("index")

	def get_object(self, *args, **kwargs):
		obj = super(DeleteFile, self).get_object(*args, **kwargs)
		assert isinstance(obj, dashboard.models.UploadedFile)
		if not obj.owner == self.request.user \
				and getattr(self.request.user, 'is_staff', False):
			raise PermissionDenied("Not authorized to delete this file")
		return obj

@staff_member_required
def quasigrader(request, num_hours = 336) -> HttpResponse:
	context : Dict[str, Any] = {}
	context['title'] = 'Quasi-grader'
	num_hours = int(num_hours)

	context['items'] = []

	num_psets = dict(roster.models.Student.objects\
			.filter(semester__active=True, legit=True)\
			.filter(uploadedfile__category='psets')\
			.annotate(num_psets = Count('uploadedfile__unit', distinct=True))\
			.values_list('id', 'num_psets'))

	uploads = dashboard.models.UploadedFile.objects\
			.filter(created_at__gte = now() - timedelta(hours=num_hours))\
			.filter(category='psets')\
			.select_related('benefactor')\
			.prefetch_related('benefactor__unlocked_units')\
			.filter(benefactor__unlocked_units=F('unit'))\
			.order_by('-created_at')

	for upload in uploads:
		# cut off filename
		if len(upload.filename) > 16:
			name = upload.filename[:12] + upload.filename[-4:]
		else:
			name = upload.filename

		d = {'student' : upload.benefactor,
				'file' : upload,
				'rows' : upload.benefactor.generate_curriculum_rows(True),
				'num_psets' : num_psets.get(upload.benefactor.id, None),
				'num_done' : upload.benefactor.num_units_done,
				'filename' : name
				}
		d['flag_num_not_one'] = d['num_psets'] is not None \
			and (d['num_psets'] - d['num_done'] != 1)
		context['items'].append(d)

	context['inquiry_nag'] = roster.models.UnitInquiry.objects\
			.filter(status='NEW', student__semester__active = True).count()
	context['suggestion_nag'] = dashboard.models.ProblemSuggestion.objects\
			.filter(resolved=False).count()
	context['num_hours'] = num_hours

	return render(request, "dashboard/quasigrader.html", context)

@staff_member_required
def idlewarn(request):
	context = {}
	context['title'] = 'Idle-warn'

	newest = dashboard.models.UploadedFile.objects\
			.filter(category='psets')\
			.filter(benefactor=OuterRef('pk'))\
			.order_by('-created_at')\
			.values('created_at')[:1]

	context['students'] = roster.utils\
			.get_visible_students(request.user)\
			.filter(legit=True)\
			.annotate(latest_pset=Subquery(newest))\
			.order_by('latest_pset')

	return render(request, "dashboard/idlewarn.html", context)

@staff_member_required
def leaderboard(request):
	context = {}
	context['title'] = 'Leader-board'

	context['students'] = roster.utils\
			.get_visible_students(request.user)\
			.filter(legit=True)\
			.annotate(num_psets = Count('uploadedfile__unit',
				filter=Q(uploadedfile__category='psets'), distinct=True))\
			.order_by('-num_units_done')
	context['num_psets_available'] = True

	return render(request, "dashboard/stulist.html", context)

class DownloadList(LoginRequiredMixin, ListView):
	template_name = 'dashboard/download_list.html'

	def get_queryset(self):
		student = get_object_or_404(roster.models.Student, id=self.kwargs['pk'])
		roster.utils.check_can_view(self.request, student)
		return dashboard.models.SemesterDownloadFile.objects.filter(semester = student.semester)

class PSetDetail(LoginRequiredMixin, DetailView):
	template_name = 'dashboard/pset_detail.html'
	model = dashboard.models.PSet
	object_name = 'pset'

class ProblemSuggestionCreate(LoginRequiredMixin, CreateView):
	context_object_name = "problem_suggestion"
	fields = ('unit', 'weight', 'source', 'description', 'statement', 'solution', 'comments', 'acknowledge',)
	model = dashboard.models.ProblemSuggestion
	def get_initial(self):
		initial = super().get_initial()
		if 'unit_id' in self.kwargs:
			initial['unit'] = self.kwargs['unit_id']
		return initial
	def form_valid(self, form):
		form.instance.student = roster.utils.get_student(self.kwargs['student_id'])
		messages.success(self.request, "Successfully submitted suggestion! Thanks much :) You can add more using the form below.")
		return super().form_valid(form)
	def get_success_url(self):
		return reverse_lazy("suggest-new", kwargs=self.kwargs)
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['student'] = roster.utils.get_student(self.kwargs['student_id'])
		return context

class ProblemSuggestionUpdate(LoginRequiredMixin, UpdateView):
	context_object_name = "problem_suggestion"
	fields = ('unit', 'weight', 'source', 'description', 'statement', 'solution', 'comments', 'acknowledge',)
	model = dashboard.models.ProblemSuggestion
	object: dashboard.models.ProblemSuggestion

	def get_success_url(self):
		return reverse_lazy("suggest-update", kwargs=self.kwargs)
	def form_valid(self, form):
		messages.success(self.request, "Edits saved.")
		return super().form_valid(form)
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['student'] = roster.utils.get_student(self.object.student.id)
		return context

class ProblemSuggestionList(LoginRequiredMixin, ListView):
	context_object_name = "problem_suggestions"
	def get_queryset(self):
		student = get_object_or_404(roster.models.Student, id=self.kwargs['student_id'])
		roster.utils.check_can_view(self.request, student)
		return dashboard.models.ProblemSuggestion.objects.filter(student=student).order_by('resolved', 'created_at')
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['student'] = roster.utils.get_student(self.kwargs['student_id'])
		return context

@staff_member_required
def pending_contributions(request, suggestion_id = None) -> HttpResponse:
	context : Dict[str, Any] = {}
	if request.method == "POST":
		if suggestion_id is None:
			return HttpResponseBadRequest("The form must include a suggestion ID")
		suggestion = get_object_or_404(dashboard.models.ProblemSuggestion, id = suggestion_id)
		form = forms.ResolveSuggestionForm(request.POST, instance = suggestion)
		if form.is_valid():
			messages.success(request, "Successfully resolved " + suggestion.source)
			suggestion = form.save(commit = False)
			suggestion.resolved = True
			suggestion.save()

	context['forms'] = []
	for suggestion in dashboard.models.ProblemSuggestion.objects.filter(resolved=False):
		form = forms.ResolveSuggestionForm(instance = suggestion)
		context['forms'].append(form)

	return render(request, "dashboard/pending_contributions.html", context)
