"""Roster views

For historical reasons (aka I didn't plan ahead),
the division between dashboard and roster is a bit weird.

* roster handles the list of students and their curriculums
* roster also handles invoices
* dashboard handles stuff and uploads and pset submissions

So e.g. "list students by most recent pset" goes under dashboard.
"""

import collections
import datetime
import logging
import os
from hashlib import pbkdf2_hmac, sha256
from typing import Any, Dict, List

from allauth.socialaccount.models import SocialAccount
from core.models import Semester, Unit
from dashboard.models import PSet
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.models import Group, User
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse  # NOQA
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic.edit import UpdateView
from mailchimp3 import MailChimp
from mailchimp3.mailchimpclient import MailChimpError

from roster.utils import can_edit, get_current_students, get_student_by_id, infer_student  # NOQA

from .forms import AdvanceForm, CurriculumForm, DecisionForm, InquiryForm, UserForm  # NOQA
from .models import Invoice, RegistrationContainer, Student, StudentRegistration, UnitInquiry  # NOQA

# Create your views here.


@login_required
def curriculum(request: HttpRequest, student_id: int) -> HttpResponse:
	student = get_student_by_id(request, student_id)
	units = Unit.objects.all()
	original = student.curriculum.values_list('id', flat=True)

	enabled = can_edit(request, student) or student.newborn
	if request.method == 'POST' and enabled:
		form = CurriculumForm(request.POST, units=units, enabled=True)
		if form.is_valid():
			data = form.cleaned_data
			# get groups with nonempty unit sets
			unit_lists = [data[k] for k in data if k.startswith('group-') and data[k] is not None]
			values = [unit for unit_list in unit_lists for unit in unit_list]
			student.curriculum.set(values)
			student.save()
			messages.success(request, f"Successfully saved curriculum of {len(values)} units.")
	else:
		form = CurriculumForm(units=units, original=original, enabled=enabled)
		if not enabled:
			messages.info(
				request, "You can't edit this curriculum " + "since you are not an instructor."
			)

	context = {
		'title': "Units for " + student.name,
		'student': student,
		'form': form,
		'enabled': enabled
	}
	# return HttpResponse("hi")
	return render(request, "roster/currshow.html", context)


@login_required
@require_POST
def finalize(request: HttpRequest, student_id: int) -> HttpResponse:
	# Removes a newborn status, thus activating everything
	student = get_student_by_id(request, student_id)
	if student.curriculum.count() > 0:
		student.newborn = False
		first_units = student.curriculum.all()[0:3]
		student.unlocked_units.set(first_units)
		student.save()
		messages.success(
			request, "Your curriculum has been finalized! "
			"You can start working now; "
			"the first three units have been unlocked."
		)
	else:
		messages.error(
			request, "You didn't select any units. "
			"You should select some units before using this link."
		)
	return HttpResponseRedirect(reverse("portal", args=(student_id, )))


@login_required
def advance(request: HttpRequest, student_id: int) -> Any:
	student = get_student_by_id(request, student_id)
	if request.method == 'POST':
		form = AdvanceForm(request.POST, instance=student)
		if form.is_valid():
			form.save()
			messages.success(request, "Successfully advanced student.")
			# uncomment the below if you want to load the portal again
			# return HttpResponseRedirect(reverse("portal", args=(student_id,)))
	else:
		form = AdvanceForm(instance=student)

	context: Dict[str, Any] = {'title': "Advance " + student.name}
	context['form'] = form
	context['student'] = student
	context['omniscient'] = can_edit(request, student)
	context['curriculum'] = student.generate_curriculum_rows(omniscient=context['omniscient'])
	if student.semester.uses_legacy_pset_system:
		uploads = student.uploadedfile_set  # type: ignore
		context['num_psets'] = uploads.filter(category='psets').values('unit').distinct().count()
	else:
		context['num_psets'] = PSet.objects.filter(student=student).count()

	return render(request, "roster/advance.html", context)


def get_checksum(student: Student) -> str:
	key = settings.INVOICE_HASH_KEY
	return pbkdf2_hmac(
		'sha256', (key + str(student.id) + 'meow').encode('utf-8'),
		b'salt is yummy so is sugar',
		100000,
		dklen=18
	).hex()


@login_required
def invoice(request: HttpRequest, student_id: int = None) -> HttpResponse:
	if student_id is None:
		student = infer_student(request)
		return HttpResponseRedirect(reverse("invoice", args=(student.id, )))

	# Now assume student_id is not None
	student = get_student_by_id(request, student_id, payment_exempt=True)

	if not student.semester.show_invoices:
		invoice = None
	else:
		try:
			invoice = student.invoice
		except ObjectDoesNotExist:
			invoice = None

	context = {
		'title': "Invoice for " + student.name,
		'student': student,
		'invoice': invoice,
		'checksum': get_checksum(student)
	}
	# return HttpResponse("hi")
	return render(request, "roster/invoice.html", context)


# this is not gated
def invoice_standalone(request: HttpRequest, student_id: int, checksum: str) -> HttpResponse:
	student = Student.objects.get(id=student_id)
	if checksum != get_checksum(student):
		raise PermissionDenied("Bad hash provided")
	try:
		invoice = student.invoice
	except ObjectDoesNotExist:
		raise Http404("No invoice exists for this student")
	context = {
		'title': "Invoice for " + student.name,
		'student': student,
		'invoice': invoice,
		'checksum': checksum
	}
	# return HttpResponse("hi")
	return render(request, "roster/invoice-standalone.html", context)


@staff_member_required
def master_schedule(request: HttpRequest) -> HttpResponse:
	student_names_and_unit_ids = get_current_students().filter(
		legit=True
	).values('user__first_name', 'user__last_name', 'curriculum')
	unit_to_student_names = collections.defaultdict(list)
	for d in student_names_and_unit_ids:
		# e.g. d = {'name': Student, 'curriculum': 30}
		name = d['user__first_name'] + ' ' + d['user__last_name']
		unit_to_student_names[d['curriculum']].append(name)

	chart: List[Dict[str, Any]] = []
	unit_dicts = Unit.objects.order_by('position').values(
		'position', 'pk', 'group__subject', 'group__name', 'code'
	)
	for unit_dict in unit_dicts:
		row = dict(unit_dict)
		row['students'] = unit_to_student_names[unit_dict['pk']]
		chart.append(row)
	semester = Semester.objects.get(active=True)
	context = {'chart': chart, 'title': "Master Schedule", 'semester': semester}
	return render(request, "roster/master-schedule.html", context)


class UpdateInvoice(PermissionRequiredMixin, UpdateView):
	permission_required = 'is_staff'
	model = Invoice
	fields = (
		'preps_taught',
		'hours_taught',
		'adjustment',
		'extras',
		'total_paid',
		'forgive',
	)
	object: Invoice

	def get_success_url(self):
		return reverse("invoice", args=(self.object.student.id, ))


# Inquiry views
@login_required
def inquiry(request: HttpRequest, student_id: int) -> HttpResponse:
	assert isinstance(request.user, User)
	student = get_student_by_id(request, student_id)
	if not student.semester.active:
		raise PermissionDenied(
			"Not an active semester, so change petitions are no longer possible."
		)
	if student.newborn:
		raise PermissionDenied(
			"This form isn't enabled yet because you have not chosen your initial units."
		)

	context: Dict[str, Any] = {}
	current_inquiries = UnitInquiry.objects.filter(student=student)

	# Create form for submitting new inquiries
	if request.method == 'POST':
		form = InquiryForm(request.POST)
		if form.is_valid():
			inquiry = form.save(commit=False)
			inquiry.student = student
			# check if exists already and created recently
			one_day_ago = timezone.now() - datetime.timedelta(seconds=90)
			if UnitInquiry.objects.filter(
				unit=inquiry.unit,
				student=student,
				action_type=inquiry.action_type,
				created_at__gte=one_day_ago,
			).exists():
				messages.warning(
					request, "The same inquiry already was "
					"submitted within the last 90 seconds."
				)
			else:
				inquiry.save()

				unlocked_count = current_inquiries.filter(
					action_type="UNLOCK", status="NEW"
				).count() + student.unlocked_units.count()

				# auto-acceptance criteria
				auto_accept_criteria = (inquiry.action_type == "APPEND")
				auto_accept_criteria |= (inquiry.action_type == "DROP")
				auto_accept_criteria |= current_inquiries.filter(action_type="UNLOCK").count() <= 3
				auto_accept_criteria |= request.user.is_staff
				auto_accept_criteria |= inquiry.action_type == "UNLOCK" and unlocked_count < 9 and (
					current_inquiries.filter(action_type="DROP", status="ACC", unit=inquiry.unit).count()
					> 0
				)

				# auto reject criteria
				auto_reject_criteria = inquiry.action_type == "UNLOCK" and unlocked_count > 9

				if auto_accept_criteria:
					inquiry.run_accept()
					messages.success(request, "Inquiry automatically approved.")
				elif auto_reject_criteria:
					inquiry.status = "REJ"
					inquiry.save()
					messages.error(
						request, "You can't have more than 9 unfinished units unlocked at once."
					)
				else:
					messages.success(request, "Inquiry submitted, should be approved soon!")
	else:
		form = InquiryForm()
	context['form'] = form

	context['inquiries'] = UnitInquiry.objects.filter(student=student)
	context['student'] = student
	context['curriculum'] = student.generate_curriculum_rows(
		omniscient=can_edit(request, student)
	)

	return render(request, 'roster/inquiry.html', context)


def mailchimp_subscribe(user: User):
	if settings.TESTING:
		return
	client = MailChimp(mc_api=os.getenv('MAILCHIMP_API_KEY'), mc_user='vEnhance')
	client.lists.members.create(
		os.getenv('MAILCHIMP_LIST_ID'), {
			'email_address': user.email,
			'status': 'subscribed',
			'merge_fields': {
				'FNAME': user.first_name,
				'LNAME': user.last_name,
			}
		}
	)


@login_required
def register(request: HttpRequest) -> HttpResponse:
	try:
		container = RegistrationContainer.objects.get(semester__active=True)
	except (RegistrationContainer.DoesNotExist, RegistrationContainer.MultipleObjectsReturned):
		return HttpResponse("There isn't a currently active OTIS semester.", status=503)

	semester: Semester = container.semester
	assert isinstance(request.user, User)
	if StudentRegistration.objects.filter(user=request.user, container=container).exists():
		messages.info(request, message="You have already submitted a decision form for this year!")
		form = None
	elif request.method == 'POST':
		form = DecisionForm(request.POST, request.FILES)
		if form.is_valid():
			passcode = form.cleaned_data['passcode']
			if passcode.lower() != container.passcode.lower():
				messages.error(request, message="Wrong passcode")
			elif form.cleaned_data['track'] not in container.allowed_tracks.split(','):
				messages.error(request, message="That track is not currently accepting registrations.")
			else:
				registration = form.save(commit=False)
				registration.container = container
				registration.user = request.user
				registration.save()
				request.user.first_name = form.cleaned_data['given_name']
				request.user.last_name = form.cleaned_data['surname']
				request.user.email = form.cleaned_data['email_address']
				group, _ = Group.objects.get_or_create(name='Verified')
				group.user_set.add(request.user)  # type: ignore
				request.user.save()
				mailchimp_subscribe(request.user)
				messages.success(request, message="Submitted! Sit tight.")
				logging.log(
					settings.ACTION_LOG_LEVEL,
					f'New registration from {request.user.first_name} {request.user.last_name}'
				)
				return HttpResponseRedirect(reverse("index"))
	else:
		if container.allowed_tracks:
			initial_data_dict = {}
			most_recent_reg = StudentRegistration.objects.filter(
				user=request.user,
			).order_by('-id').first()
			if most_recent_reg is not None:
				for k in ('parent_email', 'graduation_year', 'school_name', 'aops_username', 'gender'):
					initial_data_dict[k] = getattr(most_recent_reg, k)
			form = DecisionForm(initial=initial_data_dict)
		else:
			messages.warning(
				request,
				message="The currently active semester isn't accepting registrations right now."
			)
			form = None
	context = {'title': f'{semester} Decision Form', 'form': form, 'container': container}
	return render(request, 'roster/decision_form.html', context)


@login_required
def update_profile(request: HttpRequest) -> HttpResponse:
	assert isinstance(request.user, User)
	old_email = request.user.email
	if request.method == 'POST':
		form = UserForm(request.POST, instance=request.user)
		if form.is_valid():
			new_email = form.cleaned_data['email']
			user: User = form.save()
			if old_email != new_email:
				logging.info(
					f"User {user.first_name} {user.last_name} added {new_email} "
					f"(formerly {old_email})"
				)
				user.save()
				try:
					mailchimp_subscribe(user)
					messages.info(
						request, "Your updated email was added to the OTIS mailing list. "
						"You may want to unsubscribe the old one."
					)
				except MailChimpError as e:
					logging.error(f"Could not add {new_email} to MailChimp", exc_info=e)
					messages.warning(
						request, "The new email could not be added to MailChimp, maybe it exists already?"
					)
			else:
				user.save()
			messages.success(request, "Your information has been updated.")
	else:
		form = UserForm(instance=request.user)
	context = {'form': form}
	return render(request, "roster/update_profile.html", context)


@csrf_exempt
@require_POST
def api(request: HttpRequest) -> JsonResponse:
	if settings.PRODUCTION:
		token = request.POST.get('token')
		assert token is not None
		if not sha256(token.encode('ascii')).hexdigest() == settings.API_TARGET_HASH:
			return JsonResponse({'error': "☕"}, status=418)
	# check whether social account exists
	uid = int(request.POST['uid'])
	queryset = SocialAccount.objects.filter(uid=uid)
	if not (n := len(queryset)) == 1:
		return JsonResponse({'result': 'nonexistent', 'length': n})

	social = queryset.get()  # get the social account for this; should never 404
	user = social.user
	student = Student.objects.filter(user=user, semester__active=True).first()
	regform = StudentRegistration.objects.filter(
		user=user, container__semester__active=True
	).first()

	if student is not None:
		return JsonResponse(
			{
				'result': 'success',
				'user': social.user.username,
				'name': social.user.get_full_name(),
				'uid': uid,
				'track': student.track,
				'gender': regform.gender if regform is not None else '?',
				'country': regform.country if regform is not None else '???',
				'num_years': Student.objects.filter(user=user).count(),
			}
		)
	elif student is None and regform is not None:
		return JsonResponse({'result': 'pending'})
	else:
		return JsonResponse({'result': 'unregistered'})


# TODO ugly hack but I'm tired of answering this request
@login_required
def unlock_rest_of_mystery(request: HttpRequest, delta: int = 1) -> HttpResponse:
	student = infer_student(request)
	assert delta == 1 or delta == 2
	try:
		mystery = student.unlocked_units.get(group__name="Mystery")
	except Unit.DoesNotExist:
		s = "You don't have the Mystery unit unlocked!"
		s += "\n"
		s += f"You are currently {student}"
		return HttpResponse(s, status=403)
	added_unit = get_object_or_404(Unit, position=mystery.position + delta)
	student.unlocked_units.remove(mystery)
	student.curriculum.remove(mystery)
	student.unlocked_units.add(added_unit)
	student.curriculum.add(added_unit)
	messages.success(request, f"Added the unit {added_unit}")
	return HttpResponseRedirect('/')
