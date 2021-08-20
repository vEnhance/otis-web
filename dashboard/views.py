# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging
import os
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, Dict, List

from braces.views import LoginRequiredMixin, StaffuserRequiredMixin
from core.models import Semester, Unit
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Count, OuterRef, Q, Subquery, Sum  # NOQA
from django.db.models.expressions import Exists
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http import HttpResponse, HttpResponseRedirect  # NOQA
from django.http.request import HttpRequest
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from exams.models import ExamAttempt, PracticeExam
from mailchimp3 import MailChimp
from roster.models import Student, StudentRegistration, UnitInquiry
from roster.utils import can_edit, can_view, get_student_by_id, get_visible_students  # NOQA
from sql_util.aggregates import SubqueryCount, SubquerySum
from sql_util.utils import SubqueryAggregate

from dashboard.forms import DiamondsForm

from .forms import NewUploadForm, PSetForm
from .models import Achievement, AchievementUnlock, Level, ProblemSuggestion, PSet, SemesterDownloadFile, UploadedFile  # NOQA

logger = logging.getLogger(__name__)


class Meter:
	def __init__(
		self,
		name: str,
		emoji: str,
		value: int,
		unit: str,
		color: str,
		max_value: int,
	):
		self.name = name
		self.emoji = emoji
		self.value = value
		self.unit = unit
		self.color = color
		self.max_value = max_value

	@property
	def level(self) -> int:
		return int(self.value**0.5)

	@property
	def percent(self) -> int:
		eps = 0.2
		k = (self.value + eps * self.max_value) / ((1 + eps) * self.max_value)
		return min(100, int(100 * k))

	@property
	def needed(self) -> int:
		return (self.level + 1)**2 - self.value

	@property
	def thresh(self) -> int:
		return (self.level + 1)**2

	@property
	def total(self):
		return self.value

	@staticmethod
	def ClubMeter(value: int):
		return Meter(
			name="Dexterity", emoji="♣️", value=value, unit="♣", color='#007bff;', max_value=2500
		)

	@staticmethod
	def HeartMeter(value: int):
		return Meter(
			name="Wisdom", emoji="🕰️", value=value, unit="♥", color='#198754', max_value=2500
		)

	@staticmethod
	def SpadeMeter(value: int):
		return Meter(
			name="Strength", emoji="🏆", value=value, unit="♠", color='#ae610f', max_value=82
		)

	@staticmethod
	def DiamondMeter(value: int):
		return Meter(
			name="Charisma", emoji="㊙️", value=value, unit="◆", color='#9c1421', max_value=50
		)


def _get_meter_update(student: Student) -> Dict[str, Any]:
	psets = PSet.objects.filter(student=student, approved=True, eligible=True)
	pset_data = psets.aggregate(Sum('clubs'), Sum('hours'))
	total_diamonds = AchievementUnlock.objects.filter(user=student.user).aggregate(
		Sum('achievement__diamonds')
	)['achievement__diamonds__sum'] or 0
	quiz_data = ExamAttempt.objects.filter(student=student)
	total_spades = quiz_data.aggregate(Sum('score'))['score__sum'] or 0
	total_spades += student.usemo_score or 0
	meters = {
		'clubs': Meter.ClubMeter(pset_data['clubs__sum'] or 0),
		'hearts': Meter.HeartMeter(int(pset_data['hours__sum'] or 0)),
		'diamonds': Meter.DiamondMeter(total_diamonds),
		'spades': Meter.SpadeMeter(total_spades),  # TODO input value
	}
	level_number = sum(meter.level for meter in meters.values())
	level = Level.objects.filter(threshold__lte=level_number).order_by('-threshold').first()
	level_name = level.name if level is not None else 'No Level'
	return {
		'psets': psets,
		'pset_data': pset_data,
		'quiz_data': quiz_data,
		'meters': meters,
		'level_number': level_number,
		'level_name': level_name
	}


@login_required
def portal(request: HttpRequest, student_id: int) -> HttpResponse:
	student = get_student_by_id(request, student_id, payment_exempt=True)
	assert isinstance(request.user, User)
	if not request.user.is_staff and student.is_delinquent:
		return HttpResponseRedirect(reverse_lazy('invoice', args=(student_id, )))
	semester = student.semester

	# mailchimp
	if not settings.TESTING:
		timestamp = (timezone.now() + timedelta(days=-28))
		client = MailChimp(mc_api=os.getenv('MAILCHIMP_API_KEY'), mc_user='vEnhance')
		mailchimp_campaign_data = client.campaigns.all(
			get_all=True, status='sent', since_send_time=timestamp
		)
		if mailchimp_campaign_data is not None:
			campaigns = mailchimp_campaign_data['campaigns']
		else:
			campaigns = []
	else:
		campaigns = []

	context: Dict[str, Any] = {}
	context['title'] = f"{student.name} ({semester.name})"
	context['student'] = student
	context['semester'] = semester
	context['omniscient'] = can_edit(request, student)
	context['curriculum'] = student.generate_curriculum_rows(omniscient=context['omniscient'])
	context['tests'] = PracticeExam.objects.filter(
		is_test=True, family=semester.exam_family, due_date__isnull=False
	)
	context['quizzes'] = PracticeExam.objects.filter(
		is_test=False, family=semester.exam_family, due_date__isnull=False
	)
	context['emails'] = [
		{
			'url': c['archive_url'],
			'title': c['settings']['title'],
			'preview_text': c['settings']['preview_text'],
			'timestamp': datetime.fromisoformat(c['send_time'])
		} for c in campaigns
	]
	context['num_sem_download'] = SemesterDownloadFile.objects.filter(semester=semester).count()
	context.update(_get_meter_update(student))
	return render(request, "dashboard/portal.html", context)


@login_required
def stats(request: HttpRequest, student_id: int) -> HttpResponse:
	student = get_student_by_id(request, student_id)
	assert isinstance(student.user, User)
	context: Dict[str, Any] = {
		'student': student,
		'form': DiamondsForm(),
		'achievements': AchievementUnlock.objects.filter(user=student.user).order_by('-timestamp'),
	}
	if request.method == 'POST':
		form = DiamondsForm(request.POST)
		if form.is_valid():
			code = form.cleaned_data['code']
			if student.semester.active is False:
				messages.warning(request, "Not an active semester.")
			elif AchievementUnlock.objects.filter(user=student.user, achievement__code=code).exists():
				messages.warning(request, "You already earned this achievement!")
			else:
				try:
					achievement = Achievement.objects.get(code__iexact=code)
				except Achievement.DoesNotExist:
					messages.error(request, "You entered an invalid code.")
				else:
					logging.log(settings.SUCCESS_LOG_LEVEL, f"{student.name} obtained {achievement}")
					AchievementUnlock.objects.create(user=student.user, achievement=achievement)
					context['obtained_achievement'] = achievement
			form = DiamondsForm()
	else:
		form = DiamondsForm()
	try:
		context['first_achievement'] = Achievement.objects.get(pk=1)
	except Achievement.DoesNotExist:
		pass
	_meter_info = _get_meter_update(student)
	context.update(_meter_info)
	level_number = _meter_info['level_number']
	obtained_levels = Level.objects.filter(threshold__lte=level_number).order_by('-threshold')
	context['obtained_levels'] = obtained_levels
	return render(request, "dashboard/stats.html", context)


class AchievementList(LoginRequiredMixin, ListView):
	template_name = 'dashboard/diamond_list.html'

	def get_queryset(self) -> QuerySet[Achievement]:
		assert isinstance(self.request.user, User)
		return Achievement.objects.filter(active=True).annotate(
			num_found=SubqueryAggregate('achievementunlock', aggregate=Count),
			obtained=Exists(
				Achievement.objects.filter(
					pk=OuterRef('pk'), achievementunlock__user=self.request.user
				)
			),
		).order_by('-obtained', '-num_found')


class FoundList(LoginRequiredMixin, StaffuserRequiredMixin, ListView):
	raise_exception = True
	template_name = 'dashboard/found_list.html'

	def get_queryset(self) -> QuerySet[AchievementUnlock]:
		self.achievement = get_object_or_404(Achievement, pk=self.kwargs['pk'])
		return AchievementUnlock.objects.filter(
			achievement=self.achievement,
		).select_related('user').order_by('-timestamp')

	def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['achievement'] = self.achievement
		return context


@staff_member_required
def leaderboard(request: HttpRequest) -> HttpResponse:
	assert isinstance(request.user, User)
	students = Student.objects.filter(semester__active=True)
	rows: List[Dict[str, Any]] = []
	levels: Dict[int, str] = {level.threshold: level.name for level in Level.objects.all()}
	if len(levels) == 0:
		levels[0] = 'No level'
	max_level = max(levels.keys())
	for student in annotate_multiple_students(students):
		row: Dict[str, Any] = {}
		row['id'] = student.id
		row['name'] = student.name
		row['spades'] = (getattr(student, 'spades_quizzes', 0) or 0) + (student.usemo_score or 0)
		row['hearts'] = getattr(student, 'hearts', 0) or 0
		row['clubs'] = getattr(student, 'clubs', 0) or 0
		row['diamonds'] = getattr(student, 'diamonds', 0) or 0
		row['level'] = sum(int(row[k]**0.5) for k in ('spades', 'hearts', 'clubs', 'diamonds'))
		if row['level'] > max_level:
			row['level_name'] = levels[max_level]
		else:
			row['level_name'] = levels.get(row['level'], "No level")
		rows.append(row)
	rows.sort(
		key=lambda row: (
			-row['level'], -row['spades'], -row['hearts'], -row['clubs'], -row['diamonds'], row[
				'name'].upper()
		)
	)
	context: Dict[str, Any] = {}
	context['rows'] = rows
	return render(request, "dashboard/leaderboard.html", context)


@login_required
def submit_pset(request: HttpRequest, student_id: int) -> HttpResponse:
	student = get_student_by_id(request, student_id)
	if request.method == 'POST':
		form = PSetForm(request.POST, request.FILES)
	else:
		form = PSetForm()

	form.fields['next_unit_to_unlock'].queryset = student.generate_curriculum_queryset().filter(
		has_pset=False
	)
	form.fields['unit'].queryset = student.unlocked_units.all()
	if request.method == 'POST' and form.is_valid():
		pset = form.save(commit=False)
		if PSet.objects.filter(student=student, unit=pset.unit).exists():
			messages.error(request, "You have already submitted for this unit.")
		else:
			f = UploadedFile(
				benefactor=student,
				owner=student.user,
				category='psets',
				description='',
				content=form.cleaned_data['content'],
				unit=pset.unit,
			)
			f.save()
			pset.student = student
			pset.upload = f
			pset.save()
			messages.success(
				request, "The problem set is submitted successfully "
				"and is pending review!"
			)
			logging.log(settings.VERBOSE_LOG_LEVEL, f"{student} submitted for {pset.unit}")

	# TODO more stats
	context = {
		'title':
			'Ready to submit?',
		'student':
			student,
		'pending_psets':
			PSet.objects.filter(student=student, approved=False).order_by('-upload__created_at'),
		'approved_psets':
			PSet.objects.filter(student=student, approved=True).order_by('-upload__created_at'),
		'form':
			form,
	}
	return render(request, "dashboard/submit_pset_form.html", context)


@login_required
def uploads(request: HttpRequest, student_id: int, unit_id: int) -> HttpResponse:
	student = get_student_by_id(request, student_id)
	unit = get_object_or_404(Unit.objects, id=unit_id)
	uploads = UploadedFile.objects.filter(benefactor=student, unit=unit)
	if not student.check_unit_unlocked(unit) and not uploads.exists():
		raise PermissionDenied("This unit is not unlocked yet")

	form = None
	if request.method == "POST":
		form = NewUploadForm(request.POST, request.FILES)
		if form.is_valid():
			new_upload = form.save(commit=False)
			new_upload.unit = unit
			new_upload.benefactor = student
			new_upload.owner = request.user
			new_upload.save()
			messages.success(request, "New file has been uploaded.")
			form = None  # clear form on successful upload, prevent duplicates
	if form is None:
		form = NewUploadForm(initial={'unit': unit})

	context: Dict[str, Any] = {}
	context['title'] = 'File Uploads'
	context['student'] = student
	context['unit'] = unit
	context['form'] = form
	context['files'] = uploads
	# TODO form for adding new files
	return render(request, "dashboard/uploads.html", context)


def annotate_multiple_students(queryset: QuerySet[Student]) -> QuerySet[Student]:
	"""Helper function for constructing large lists of students
	Selects all important information to prevent a bunch of SQL queries"""
	return queryset.select_related('user', 'assistant', 'semester').annotate(
		num_psets=SubqueryCount('pset', filter=Q(approved=True, eligible=True)),
		clubs=SubquerySum('pset__clubs', filter=Q(approved=True, eligible=True)),
		hearts=SubquerySum('pset__hours', filter=Q(approved=True, eligible=True)),
		spades_quizzes=SubquerySum('examattempt__score'),
		diamonds=SubquerySum('user__achievementunlock__achievement__diamonds'),
	)


@login_required
def index(request: HttpRequest) -> HttpResponse:
	assert isinstance(request.user, User)
	students = get_visible_students(request.user, current=True)
	if len(students) == 1:  # unique match
		return HttpResponseRedirect(reverse("portal", args=(students[0].id, )))
	assert isinstance(request.user, User)
	context: Dict[str, Any] = {}
	context['title'] = "Current Semester Listing"
	context['students'] = annotate_multiple_students(students).order_by(
		'track', 'user__first_name', 'user__last_name'
	)
	context['stulist_show_semester'] = False
	context['submitted_registration'] = StudentRegistration.objects.filter(
		user=request.user, container__semester__active=True
	).exists()
	return render(request, "dashboard/stulist.html", context)


@login_required
def past(request: HttpRequest, semester: Semester = None):
	assert isinstance(request.user, User)
	students = get_visible_students(request.user, current=False)
	if semester is not None:
		students = students.filter(semester=semester)
	context: Dict[str, Any] = {}
	context['title'] = "Previous Semester Listing"
	context['students'] = annotate_multiple_students(students).order_by(
		'-semester', 'user__first_name', 'user__last_name'
	)
	context['stulist_show_semester'] = True
	context['past'] = True
	return render(request, "dashboard/stulist.html", context)


class UpdateFile(LoginRequiredMixin, UpdateView):
	model = UploadedFile
	fields = (
		'category',
		'content',
		'description',
	)
	object: UploadedFile

	def get_success_url(self):
		stu_id = self.object.benefactor.id
		unit_id = self.object.unit.id if self.object.unit is not None else 0
		return reverse(
			"uploads", args=(
				stu_id,
				unit_id,
			)
		)

	def get_object(self, *args: Any, **kwargs: Any) -> UploadedFile:
		obj = super(UpdateFile, self).get_object(*args, **kwargs)
		assert isinstance(obj, UploadedFile)
		if not obj.owner == self.request.user and getattr(self.request.user, 'is_staff', False):
			raise PermissionDenied("Not authorized to update this file")
		return obj


class DeleteFile(LoginRequiredMixin, DeleteView):
	model = UploadedFile
	success_url = reverse_lazy("index")

	def get_object(self, *args: Any, **kwargs: Any) -> UploadedFile:
		obj = super(DeleteFile, self).get_object(*args, **kwargs)
		assert isinstance(obj, UploadedFile)
		if not obj.owner == self.request.user and getattr(self.request.user, 'is_staff', False):
			raise PermissionDenied("Not authorized to delete this file")
		return obj


@staff_member_required
def idlewarn(request: HttpRequest) -> HttpResponse:
	assert isinstance(request.user, User)
	context: Dict[str, Any] = {}
	context['title'] = 'Idle-warn'

	newest_qset = UploadedFile.objects.filter(category='psets', benefactor=OuterRef('pk'))
	newest = newest_qset.order_by('-created_at').values('created_at')[:1]

	students = annotate_multiple_students(get_visible_students(request.user).filter(legit=True))
	context['students'] = students.annotate(latest_pset=Subquery(newest)).order_by('latest_pset')

	return render(request, "dashboard/idlewarn.html", context)


class DownloadList(LoginRequiredMixin, ListView):
	template_name = 'dashboard/download_list.html'

	def get_queryset(self) -> QuerySet[SemesterDownloadFile]:
		student = get_student_by_id(self.request, self.kwargs['pk'])
		return SemesterDownloadFile.objects.filter(semester=student.semester)


class PSetDetail(LoginRequiredMixin, DetailView):
	template_name = 'dashboard/pset_detail.html'
	model = PSet
	object_name = 'pset'

	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		pset = self.get_object()
		assert isinstance(pset, PSet)
		if not can_view(request, pset.student):
			raise PermissionDenied("Can't view work by this student")
		return super(DetailView, self).dispatch(request, *args, **kwargs)


class ProblemSuggestionCreate(LoginRequiredMixin, CreateView):
	context_object_name = "problem_suggestion"
	fields = (
		'unit',
		'weight',
		'source',
		'description',
		'statement',
		'solution',
		'comments',
		'acknowledge',
	)
	model = ProblemSuggestion

	def get_initial(self):
		initial = super().get_initial()
		if 'unit_id' in self.kwargs:
			initial['unit'] = self.kwargs['unit_id']
		return initial

	def form_valid(self, form: BaseModelForm):
		form.instance.student = get_student_by_id(self.request, self.kwargs['student_id'])
		messages.success(
			self.request,
			"Successfully submitted suggestion! Thanks much :) You can add more using the form below."
		)
		return super().form_valid(form)

	def get_success_url(self):
		return reverse_lazy("suggest-new", kwargs=self.kwargs)

	def get_context_data(self, **kwargs: Any):
		context = super().get_context_data(**kwargs)
		context['student'] = get_student_by_id(self.request, self.kwargs['student_id'])
		return context


class ProblemSuggestionUpdate(LoginRequiredMixin, UpdateView):
	context_object_name = "problem_suggestion"
	fields = (
		'unit',
		'weight',
		'source',
		'description',
		'statement',
		'solution',
		'comments',
		'acknowledge',
	)
	model = ProblemSuggestion
	object: ProblemSuggestion

	def get_success_url(self):
		return reverse_lazy("suggest-update", kwargs=self.kwargs)

	def form_valid(self, form: BaseModelForm):
		messages.success(self.request, "Edits saved.")
		return super().form_valid(form)

	def get_context_data(self, **kwargs: Any):
		context = super().get_context_data(**kwargs)
		context['student'] = self.object.student
		if not can_view(self.request, self.object.student):
			raise PermissionError("Logged-in user cannot view suggestions made by this student")
		return context


class ProblemSuggestionList(LoginRequiredMixin, ListView):
	context_object_name = "problem_suggestions"

	def get_queryset(self):
		student = get_student_by_id(self.request, self.kwargs['student_id'])
		self.student = student
		return ProblemSuggestion.objects.filter(student=student).order_by('resolved', 'created_at')

	def get_context_data(self, **kwargs: Any):
		context = super().get_context_data(**kwargs)
		context['student'] = self.student
		return context


@csrf_exempt
@require_POST
def api(request: HttpRequest) -> JsonResponse:
	if settings.PRODUCTION:
		token = request.POST.get('token')
		assert token is not None
		if not sha256(token.encode('ascii')).hexdigest() == settings.API_TARGET_HASH:
			return JsonResponse({'error': "☕"}, status=418)

	action = request.POST.get('action', None)

	if action == 'grade_problem_set':
		# mark problem set as done
		pset = get_object_or_404(PSet, pk=request.POST['pk'])
		pset.approved = bool(request.POST['approved'])
		pset.clubs = request.POST.get('clubs', None)
		pset.hours = request.POST.get('hours', None)
		pset.save()
		# unlock the unit the student asked for
		finished_unit = get_object_or_404(Unit, pk=request.POST['unit__pk'])
		student = get_object_or_404(Student, pk=request.POST['student__pk'])
		if 'next_unit_to_unlock__pk' not in request.POST:
			unlockable_units = student.generate_curriculum_queryset().exclude(has_pset=True).exclude(
				id__in=student.unlocked_units.all()
			)
			target = unlockable_units.first()
		else:
			target = get_object_or_404(Unit, pk=request.POST['next_unit_to_unlock__pk'])
		if target is not None:
			student.unlocked_units.add(target)
		student.unlocked_units.remove(finished_unit)
		return JsonResponse({'result': 'success'}, status=200)
	elif action == 'approve_inquiries':
		for inquiry in UnitInquiry.objects.filter(status="NEW", student__semester__active=True):
			inquiry.run_accept()
		return JsonResponse({'result': 'success'}, status=200)
	elif action == 'mark_suggestion':
		suggestion = ProblemSuggestion.objects.get(pk=request.POST['pk'])
		suggestion.reason = request.POST['reason']
		suggestion.resolved = True
		suggestion.save()
		return JsonResponse({'result': 'success'}, status=200)
	elif action == 'init':
		data: Dict[str, Any] = {
			'_name':
				'Root',
			'_children':
				[
					{
						'_name':
							'Problem sets',
						'_children':
							list(
								PSet.objects.filter(approved=False, student__semester__active=True).values(
									'pk',
									'approved',
									'feedback',
									'special_notes',
									'student__pk',
									'student__user__first_name',
									'student__user__last_name',
									'student__user__email',
									'hours',
									'clubs',
									'eligible',
									'unit__group__name',
									'unit__code',
									'unit__pk',
									'next_unit_to_unlock__group__name',
									'next_unit_to_unlock__code',
									'next_unit_to_unlock__pk',
									'upload__content',
								)
							)
					}, {
						'_name':
							'Inquiries',
						'inquiries':
							list(
								UnitInquiry.objects.filter(status="NEW", student__semester__active=True).values(
									'pk',
									'unit__group__name',
									'unit__code',
									'student__user__first_name',
									'student__user__last_name',
									'explanation',
								)
							),
					}, {
						'_name':
							'Suggestions',
						'_children':
							list(
								ProblemSuggestion.objects.filter(resolved=False).values(
									'pk',
									'created_at',
									'student__user__first_name',
									'student__user__last_name',
									'source',
									'description',
									'statement',
									'solution',
									'comments',
									'acknowledge',
									'weight',
								)
							)
					}
				],
		}
		return JsonResponse(data, status=200)
	else:
		return JsonResponse({'error': 'No such command'}, status=400)
