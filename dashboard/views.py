# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging
from datetime import timedelta
from typing import Any, Dict

from braces.views import LoginRequiredMixin, StaffuserRequiredMixin, SuperuserRequiredMixin  # NOQA
from core.models import Semester, Unit, UserProfile
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied, SuspiciousOperation
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
from markets.models import Market
from otisweb.utils import AuthHttpRequest, get_mailchimp_campaigns
from roster.models import Student, StudentRegistration
from roster.utils import can_edit, can_view, get_student_by_id, get_visible_students  # NOQA
from sql_util.utils import SubqueryAggregate

from dashboard.forms import DiamondsForm, PSetResubmitForm
from dashboard.levelsys import LevelInfoDict, get_student_rows
from dashboard.models import PalaceCarving
from dashboard.utils import get_days_since, get_units_to_submit, get_units_to_unlock  # NOQA

from .forms import NewUploadForm, PSetSubmitForm
from .levelsys import annotate_student_queryset_with_scores, check_level_up, get_level_info  # NOQA
from .models import Achievement, AchievementUnlock, Level, ProblemSuggestion, PSet, SemesterDownloadFile, UploadedFile  # NOQA

logger = logging.getLogger(__name__)


@login_required
def portal(request: AuthHttpRequest, student_id: int) -> HttpResponse:
	student = get_student_by_id(request, student_id, payment_exempt=True)
	if not request.user.is_staff and student.is_delinquent:
		return HttpResponseRedirect(reverse_lazy('invoice', args=(student_id, )))
	semester = student.semester
	profile, _ = UserProfile.objects.get_or_create(user=request.user)
	student_profile, _ = UserProfile.objects.get_or_create(user=student.user)

	level_info = get_level_info(student)
	if request.user == student.user:
		result = check_level_up(student)
		if result is True and profile.show_bars is True:
			lvl = level_info['level_number']
			messages.success(request, f"You leveled up! You're now level {lvl}.")

	context: Dict[str, Any] = {}
	context['title'] = f"{student.name} ({semester.name})"
	context['last_seen'] = student_profile.last_seen
	context['student'] = student
	context['semester'] = semester
	context['profile'] = profile
	context['omniscient'] = can_edit(request, student)
	context['curriculum'] = student.generate_curriculum_rows(omniscient=context['omniscient'])
	context['tests'] = PracticeExam.objects.filter(
		is_test=True, family=semester.exam_family, due_date__isnull=False
	)
	context['quizzes'] = PracticeExam.objects.filter(
		is_test=False, family=semester.exam_family, due_date__isnull=False
	)
	context['emails'] = [
		e for e in get_mailchimp_campaigns(14) if e['timestamp'] >= profile.last_email_dismiss
	]
	context['downloads'] = SemesterDownloadFile.objects.filter(
		semester=semester,
		created_at__gte=profile.last_download_dismiss,
	).filter(
		created_at__gte=timezone.now() - timedelta(days=14),
	)
	context['markets'] = Market.active.all()
	context['num_sem_downloads'] = SemesterDownloadFile.objects.filter(semester=semester).count()

	context.update(level_info)
	return render(request, "dashboard/portal.html", context)


@login_required
def stats(request: AuthHttpRequest, student_id: int) -> HttpResponse:
	student = get_student_by_id(request, student_id)
	unlocks = AchievementUnlock.objects.filter(user=student.user)
	unlocks = unlocks.select_related('achievement').order_by('-timestamp')
	context: Dict[str, Any] = {
		'student': student,
		'form': DiamondsForm(),
		'achievements': unlocks,
	}
	if request.method == 'POST':
		assert student.user is not None
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
					logger.warn(f"Invalid diamond code `{code}`", extra={'request': request})
				else:
					logger.log(
						SUCCESS_LOG_LEVEL,
						f"{student.name} obtained {achievement}",
						extra={'request': request}
					)
					AchievementUnlock.objects.create(user=student.user, achievement=achievement)
					context['obtained_achievement'] = achievement
			form = DiamondsForm()
	else:
		form = DiamondsForm()
	try:
		context['first_achievement'] = Achievement.objects.get(pk=1)
	except Achievement.DoesNotExist:
		pass
	level_info = get_level_info(student)
	context.update(level_info)
	level_number = level_info['level_number']
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


class FoundList(LoginRequiredMixin, StaffuserRequiredMixin, ListView[AchievementUnlock]):
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
def leaderboard(request: AuthHttpRequest) -> HttpResponse:
	students = Student.objects.filter(semester__active=True)
	rows = get_student_rows(students)
	rows.sort(
		key=lambda row: (
			-row['level'],
			-row['clubs'],
			-row['hearts'],
			-row['spades'],
			-row['diamonds'],
			row['student'].name.upper(),
		)
	)
	for row in rows:
		row['days_since_last_seen'] = get_days_since(row['last_seen'])
	context: Dict[str, Any] = {}
	context['rows'] = rows
	return render(request, "dashboard/leaderboard.html", context)


@login_required
def submit_pset(request: HttpRequest, student_id: int) -> HttpResponse:
	student = get_student_by_id(request, student_id)
	if request.method == 'POST':
		form = PSetSubmitForm(request.POST, request.FILES)
	else:
		form = PSetSubmitForm()

	form.fields['unit'].queryset = get_units_to_submit(student)
	form.fields['next_unit_to_unlock'].queryset = get_units_to_unlock(student)
	if request.method == 'POST' and form.is_valid():
		pset = form.save(commit=False)
		if PSet.objects.filter(student=student, unit=pset.unit).exists():
			messages.error(
				request, "You have already submitted for this unit. "
				"If this is intentional, you should use the resubmit button "
				"at the bottom of this page instead."
			)
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
			logger.log(
				VERBOSE_LOG_LEVEL, f"{student} submitted for {pset.unit}", extra={'request': request}
			)
			return HttpResponseRedirect(pset.get_absolute_url())

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
def resubmit_pset(request: HttpRequest, pk: int) -> HttpResponse:
	pset = get_object_or_404(PSet, pk=pk)
	student = pset.student
	if not can_view(request, student):
		raise PermissionDenied("You are missing privileges for this problem set")

	if request.method == 'POST':
		form = PSetResubmitForm(request.POST, request.FILES, instance=pset)
	else:
		form = PSetResubmitForm(instance=pset)

	if request.method == 'POST' and form.is_valid():
		pset = form.save(commit=False)
		assert pset.upload is not None
		pset.upload.content = form.cleaned_data['content']
		pset.upload.save()
		if pset.approved is True:
			pset.approved = False
			pset.resubmitted = True
		pset.save()
		messages.success(
			request, "The problem set is submitted successfully "
			"and is pending review!"
		)
		logger.log(
			VERBOSE_LOG_LEVEL, f"{student} re-submitted {pset.unit}", extra={'request': request}
		)
		return HttpResponseRedirect(pset.get_absolute_url())
	context = {
		'title': f'Resubmit {pset.unit}',
		'student': student,
		'pset': pset,
		'form': form,
	}
	return render(request, "dashboard/resubmit_pset_form.html", context)


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
		student = students.first()
		assert student is not None
		return HttpResponseRedirect(reverse("portal", args=(student.id, )))
	queryset = annotate_student_queryset_with_scores(students).order_by(
		'track', 'user__first_name', 'user__last_name'
	)
	context: Dict[str, Any] = {}
	context['title'] = "Current Semester Listing"
	context['rows'] = get_student_rows(queryset)
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
	queryset = annotate_student_queryset_with_scores(students).order_by(
		'track', 'user__first_name', 'user__last_name'
	)
	context: Dict[str, Any] = {}
	context['title'] = "Previous Semester Listing"
	context['rows'] = get_student_rows(queryset)
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

	queryset = annotate_student_queryset_with_scores(
		get_visible_students(request.user).filter(legit=True)
	)
	queryset = queryset.annotate(latest_pset=Subquery(newest))  # type: ignore
	rows = get_student_rows(queryset)
	for row in rows:
		row['days_since_last_seen'] = get_days_since(row['last_seen'])
		row['days_since_last_pset'] = get_days_since(row['student'].latest_pset)
	rows.sort(key=lambda row: -(row['days_since_last_pset'] or 1e9))
	context['rows'] = rows

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
		assert isinstance(self.request.user, User)
		form.instance.user = self.request.user
		messages.success(
			self.request,
			"Successfully submitted suggestion! Thanks much :) You can add more using the form below."
		)
		return super().form_valid(form)

	def get_success_url(self):
		return reverse_lazy("suggest-new", kwargs=self.kwargs)


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
		assert isinstance(self.request.user, User)
		if not (self.request.user.is_staff or self.request.user == self.object.user):
			raise PermissionError("Logged-in user cannot view this suggestion")
		return context


class ProblemSuggestionList(LoginRequiredMixin, ListView[ProblemSuggestion]):
	context_object_name = "problem_suggestions"

	def get_queryset(self):
		assert isinstance(self.request.user, User)
		queryset = ProblemSuggestion.objects.filter(user=self.request.user)
		queryset = queryset.order_by('resolved', 'created_at')
		return queryset


def assert_maxed_out_level_info(student: Student) -> LevelInfoDict:
	level_info = get_level_info(student)
	if not level_info['is_maxed']:
		raise PermissionDenied("Insufficient level")
	return level_info


class PalaceList(LoginRequiredMixin, ListView[PalaceCarving]):
	model = PalaceCarving
	context_object_name = "palace_carvings"
	template_name = 'dashboard/palace.html'

	def get_queryset(self):
		student = get_student_by_id(self.request, self.kwargs['student_id'])
		assert_maxed_out_level_info(student)
		self.student = student
		queryset = PalaceCarving.objects.filter(visible=True)
		queryset = queryset.exclude(display_name="")
		queryset = queryset.order_by('created_at')
		return queryset

	def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['student'] = self.student
		return context


class AdminPalaceList(SuperuserRequiredMixin, ListView[PalaceCarving]):
	model = PalaceCarving
	context_object_name = "palace_carvings"
	template_name = 'dashboard/palace.html'

	def get_queryset(self):
		queryset = PalaceCarving.objects.filter(visible=True)
		queryset = queryset.exclude(display_name="")
		queryset = queryset.order_by('created_at')
		return queryset


class PalaceUpdate(
	LoginRequiredMixin,
	SuccessMessageMixin,
	UpdateView[PalaceCarving, BaseModelForm[PalaceCarving]],
):
	model = PalaceCarving
	fields = (
		'display_name',
		'hyperlink',
		'message',
		'visible',
		'image',
	)
	template_name = 'dashboard/palace_form.html'
	success_message = "Edited palace carving successfully"

	def get_object(self, *args: Any, **kwargs: Any) -> PalaceCarving:
		student = get_student_by_id(self.request, self.kwargs['student_id'])
		assert_maxed_out_level_info(student)
		self.student = student
		carving, is_created = PalaceCarving.objects.get_or_create(student=student)
		if is_created is True:
			carving.display_name = student.name
		return carving

	def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['student'] = self.student
		return context


class DiamondUpdate(
	LoginRequiredMixin,
	UpdateView[Achievement, BaseModelForm[Achievement]],
):
	model = Achievement
	fields = (
		'code',
		'name',
		'image',
		'description',
	)
	success_message = "Updated diamond successfully."

	def get_object(self, *args: Any, **kwargs: Any) -> Achievement:
		student = get_student_by_id(self.request, self.kwargs['student_id'])
		if not student.semester.active:
			raise PermissionDenied("The palace can't be edited through an inactive student")
		assert_maxed_out_level_info(student)
		self.student = student
		achievement, _ = Achievement.objects.get_or_create(creator=student)
		return achievement

	def form_valid(self, form: BaseModelForm[Achievement]):
		level_info = assert_maxed_out_level_info(self.student)
		form.instance.diamonds = level_info['meters']['diamonds'].level
		form.instance.creator = self.student
		messages.success(
			self.request,
			f"Successfully forged diamond worth {form.instance.diamonds}◆, your current charisma level.",
		)
		return super().form_valid(form)

	def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['student'] = self.student
		return context

	def get_success_url(self):
		return reverse_lazy("diamond-update", args=(self.student.id, ))


def certify(request: HttpRequest, student_id: int, checksum: str = None):
	student = get_object_or_404(Student, pk=student_id)
	if checksum is None:
		if can_view(request, student):
			checksum = student.get_checksum(settings.CERT_HASH_KEY)
			return HttpResponseRedirect(reverse_lazy('certify', args=(student.id, checksum)))
		else:
			raise SuspiciousOperation("Not authorized to generate checksum")
	elif checksum != student.get_checksum(settings.CERT_HASH_KEY):
		raise SuspiciousOperation("Wrong hash")
	else:
		level_info = get_level_info(student)
		context = {
			'student':
				student,
			'hearts':
				level_info['meters']['hearts'].value,
			'level_number':
				level_info['level_number'],
			'level_name':
				level_info['level_name'],
			'checksum':
				student.get_checksum(settings.CERT_HASH_KEY),
			'target_url':
				f'{request.scheme}//{request.get_host()}' +
				reverse_lazy('certify', args=(student.id, checksum))
		}
		return render(request, "dashboard/certify.html", context)
