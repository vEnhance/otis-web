# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

from braces.views import LoginRequiredMixin, StaffuserRequiredMixin
from core.models import Semester, Unit
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Count, OuterRef, Subquery
from django.db.models.expressions import Exists
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http import HttpResponse, HttpResponseRedirect
from django.http.request import HttpRequest
from django.http.response import HttpResponseBase
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from dwhandler import SUCCESS_LOG_LEVEL, VERBOSE_LOG_LEVEL
from exams.models import PracticeExam
from mailchimp3 import MailChimp
from otisweb.utils import AuthHttpRequest
from roster.models import Student, StudentRegistration
from roster.utils import can_edit, can_view, get_student_by_id, get_visible_students, infer_student  # NOQA
from sql_util.utils import SubqueryAggregate

from dashboard.forms import DiamondsForm
from dashboard.levelsys import get_student_rows

from .forms import NewUploadForm, PSetForm
from .levelsys import annotate_student_queryset_with_scores, get_meters
from .models import Achievement, AchievementUnlock, Level, ProblemSuggestion, PSet, SemesterDownloadFile, UploadedFile  # NOQA

logger = logging.getLogger(__name__)


@login_required
def portal(request: AuthHttpRequest, student_id: int) -> HttpResponse:
	student = get_student_by_id(request, student_id, payment_exempt=True)
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
			'title': c['settings']['subject_line'],
			'preview_text': c['settings']['preview_text'],
			'timestamp': datetime.fromisoformat(c['send_time'])
		} for c in campaigns
	]
	context['num_sem_download'] = SemesterDownloadFile.objects.filter(semester=semester).count()
	context.update(get_meters(student))
	return render(request, "dashboard/portal.html", context)


@login_required
def stats(request: AuthHttpRequest, student_id: int) -> HttpResponse:
	student = get_student_by_id(request, student_id)
	context: Dict[str, Any] = {
		'student': student,
		'form': DiamondsForm(),
		'achievements': AchievementUnlock.objects.filter(user=student.user).order_by('-timestamp'),
	}
	if request.method == 'POST':
		form = DiamondsForm(request.POST)
		if form.is_valid():
			code = form.cleaned_data['code']
			if AchievementUnlock.objects.filter(user=student.user, achievement__code=code).exists():
				messages.warning(request, "You already earned this achievement!")
			else:
				try:
					achievement = Achievement.objects.get(code__iexact=code)
				except Achievement.DoesNotExist:
					messages.error(request, "You entered an invalid code.")
				else:
					logging.log(SUCCESS_LOG_LEVEL, f"{student.name} obtained {achievement}")
					AchievementUnlock.objects.create(user=student.user, achievement=achievement)
					context['obtained_achievement'] = achievement
			form = DiamondsForm()
	else:
		form = DiamondsForm()
	try:
		context['first_achievement'] = Achievement.objects.get(pk=1)
	except Achievement.DoesNotExist:
		pass
	_meter_info = get_meters(student)
	context.update(_meter_info)
	level_number = _meter_info['level_number']
	obtained_levels = Level.objects.filter(threshold__lte=level_number).order_by('-threshold')
	context['obtained_levels'] = obtained_levels
	return render(request, "dashboard/stats.html", context)


class AchievementList(LoginRequiredMixin, ListView[Achievement]):
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


class FoundList(LoginRequiredMixin, StaffuserRequiredMixin, ListView[Achievement]):
	raise_exception = True
	template_name = 'dashboard/found_list.html'

	def get_queryset(self) -> QuerySet[Achievement]:
		self.achievement = get_object_or_404(Achievement, pk=self.kwargs['pk'])
		return AchievementUnlock.objects.filter(
			achievement=self.achievement,
		).select_related('user').order_by('-timestamp')

	def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['achievement'] = self.achievement
		return context


@staff_member_required
def leaderboard(request: AuthHttpRequest) -> HttpResponse:
	students = Student.objects.filter(semester__active=True)
	rows = get_student_rows(students)
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
			logging.log(VERBOSE_LOG_LEVEL, f"{student} submitted for {pset.unit}")

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
	unit = get_object_or_404(Unit, id=unit_id)
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


@login_required
def index(request: AuthHttpRequest) -> HttpResponse:
	students = get_visible_students(request.user, current=True)
	if len(students) == 1:  # unique match
		return HttpResponseRedirect(reverse("portal", args=(students[0].id, )))
	context: Dict[str, Any] = {}
	context['title'] = "Current Semester Listing"
	context['students'] = annotate_student_queryset_with_scores(students).order_by(
		'track', 'user__first_name', 'user__last_name'
	)
	context['stulist_show_semester'] = False
	context['submitted_registration'] = StudentRegistration.objects.filter(
		user=request.user, container__semester__active=True
	).exists()
	return render(request, "dashboard/stulist.html", context)


@login_required
def past(request: AuthHttpRequest, semester: Semester = None):
	students = get_visible_students(request.user, current=False)
	if semester is not None:
		students = students.filter(semester=semester)
	context: Dict[str, Any] = {}
	context['title'] = "Previous Semester Listing"
	context['students'] = annotate_student_queryset_with_scores(students).order_by(
		'-semester', 'user__first_name', 'user__last_name'
	)
	context['stulist_show_semester'] = True
	context['past'] = True
	return render(request, "dashboard/stulist.html", context)


class UpdateFile(LoginRequiredMixin, UpdateView[UploadedFile, BaseModelForm[UploadedFile]]):
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
		is_staff = getattr(self.request.user, 'is_staff', False)
		if obj.owner != self.request.user and is_staff is False:
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
def idlewarn(request: AuthHttpRequest) -> HttpResponse:
	context: Dict[str, Any] = {}
	context['title'] = 'Idle-warn'

	newest_qset = UploadedFile.objects.filter(category='psets', benefactor=OuterRef('pk'))
	newest = newest_qset.order_by('-created_at').values('created_at')[:1]

	students = annotate_student_queryset_with_scores(
		get_visible_students(request.user).filter(legit=True)
	)
	students = students.annotate(latest_pset=Subquery(newest))  # type: ignore
	students = students.order_by('latest_pset')
	context['students'] = students

	return render(request, "dashboard/idlewarn.html", context)


class DownloadList(LoginRequiredMixin, ListView[SemesterDownloadFile]):
	template_name = 'dashboard/download_list.html'

	def get_queryset(self) -> QuerySet[SemesterDownloadFile]:
		student = get_student_by_id(self.request, self.kwargs['pk'])
		return SemesterDownloadFile.objects.filter(semester=student.semester)


class PSetDetail(LoginRequiredMixin, DetailView[PSet]):
	template_name = 'dashboard/pset_detail.html'
	model = PSet
	object_name = 'pset'

	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
		pset = self.get_object()
		assert isinstance(pset, PSet)
		if not can_view(request, pset.student):
			raise PermissionDenied("Can't view work by this student")
		return super(DetailView, self).dispatch(request, *args, **kwargs)


class ProblemSuggestionCreate(
	LoginRequiredMixin, CreateView[ProblemSuggestion, BaseModelForm[ProblemSuggestion]]
):
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

	def form_valid(self, form: BaseModelForm[ProblemSuggestion]):
		if 'student_id' in self.kwargs:
			form.instance.student = get_student_by_id(self.request, self.kwargs['student_id'])
		else:
			form.instance.student = infer_student(self.request)
		messages.success(
			self.request,
			"Successfully submitted suggestion! Thanks much :) You can add more using the form below."
		)
		return super().form_valid(form)

	def get_success_url(self):
		return reverse_lazy("suggest-new", kwargs=self.kwargs)

	def get_context_data(self, **kwargs: Any):
		context = super().get_context_data(**kwargs)
		if 'student_id' in self.kwargs:
			context['student'] = get_student_by_id(self.request, self.kwargs['student_id'])
		else:
			context['student'] = infer_student(self.request)
		return context


class ProblemSuggestionUpdate(
	LoginRequiredMixin, UpdateView[ProblemSuggestion, BaseModelForm[ProblemSuggestion]]
):
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

	def form_valid(self, form: BaseModelForm[ProblemSuggestion]):
		messages.success(self.request, "Edits saved.")
		return super().form_valid(form)

	def get_context_data(self, **kwargs: Any):
		context = super().get_context_data(**kwargs)
		context['student'] = self.object.student
		if not can_view(self.request, self.object.student):
			raise PermissionError("Logged-in user cannot view suggestions made by this student")
		return context


class ProblemSuggestionList(LoginRequiredMixin, ListView[ProblemSuggestion]):
	context_object_name = "problem_suggestions"

	def get_queryset(self):
		student = get_student_by_id(self.request, self.kwargs['student_id'])
		self.student = student
		return ProblemSuggestion.objects.filter(student=student).order_by('resolved', 'created_at')

	def get_context_data(self, **kwargs: Any):
		context = super().get_context_data(**kwargs)
		context['student'] = self.student
		return context
