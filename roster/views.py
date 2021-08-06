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
from hashlib import pbkdf2_hmac, sha256

import core
import core.models
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db.models import Count, IntegerField, OuterRef, Subquery
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse  # NOQA
from django.http.response import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import ListView
from django.views.generic.edit import UpdateView

from roster.utils import can_edit, get_current_students, get_student_by_id, infer_student  # NOQA

from . import forms, models

# Create your views here.

@login_required
def curriculum(request : HttpRequest, student_id):
	student = get_student_by_id(request, student_id)
	units = core.models.Unit.objects.all()
	original = student.curriculum.values_list('id', flat=True)

	enabled = can_edit(request, student) or student.newborn
	if request.method == 'POST' and enabled:
		form = forms.CurriculumForm(request.POST, units = units, enabled = True)
		if form.is_valid():
			data = form.cleaned_data
			# get groups with nonempty unit sets
			unit_lists = [data[k] for k in data if k.startswith('group-')
					and data[k] is not None]
			values = [unit for unit_list in unit_lists for unit in unit_list]
			student.curriculum.set(values)
			student.save()
			messages.success(request,
					f"Successfully saved curriculum of {len(values)} units.")
	else:
		form = forms.CurriculumForm(units = units,
				original = original, enabled = enabled)
		if not enabled:
			messages.info(request, "You can't edit this curriculum " \
					"since you are not an instructor.")

	context = {'title' : "Units for " + student.name,
			'student' : student, 'form' : form, 'enabled' : enabled}
	# return HttpResponse("hi")
	return render(request, "roster/currshow.html", context)

@login_required
@require_POST
def finalize(request, student_id):
	# Removes a newborn status, thus activating everything
	student = get_student_by_id(request, student_id)
	if student.curriculum.count() > 0:
		student.newborn = False
		first_units = student.curriculum.all()[0:3]
		student.unlocked_units.set(first_units)
		student.save()
		messages.success(request, "Your curriculum has been finalized! "
				"You can start working now; "
				"the first three units have been unlocked.")
	else:
		messages.error(request, "You didn't select any units. "
				"You should select some units before using this link.")
	return HttpResponseRedirect(reverse("portal", args=(student_id,)))

@login_required
def auto_advance(request, student_id, unit_id, target_id = None):
	student = get_student_by_id(request, student_id)
	unit = get_object_or_404(core.models.Unit, id = unit_id)

	if not student.unlocked_units.filter(id=unit_id).exists() \
			or not student.curriculum.filter(id=unit_id).exists():
		messages.error(request,
				f"The unit {unit} is not valid for auto-unlock.")
		return HttpResponseRedirect(reverse("advance", args=(student_id,)))

	unlockable_units = student.generate_curriculum_queryset()\
			.exclude(has_pset = True)\
			.exclude(id__in = student.unlocked_units.all())

	if target_id is None:
		target = unlockable_units.first()
		if target is not None:
			student.unlocked_units.add(target)
		student.unlocked_units.remove(unit)
		student.num_units_done += 1
		student.save()
		replace = False
	else:
		target = get_object_or_404(core.models.Unit, id = target_id)
		if student.unlocked_units.filter(id=target_id).exists() \
				or not student.curriculum.filter(id=target_id).exists():
			messages.error(request,
					f"The unit {target} is not valid for replacement.")
			return HttpResponseRedirect(reverse("advance", args=(student_id,)))

		student.unlocked_units.remove(unit)
		student.unlocked_units.add(target)
		replace = True

	context = {}
	context["target"] = target
	if context["target"]:
		context["title"] = f"{'Toggled' if replace else 'Unlocked'} {target} for {student.first_name}"
	else:
		context["title"] = student.name + " is done!"
	context["replace"] = replace
	context["finished"] = str(unit)
	context["student"] = student
	context["alternatives"] = unlockable_units
	return render(request, "roster/auto-advance.html", context)

@login_required
def advance(request, student_id):
	student = get_student_by_id(request, student_id)
	if request.method == 'POST':
		form = forms.AdvanceForm(request.POST, instance = student)
		if form.is_valid():
			form.save()
			messages.success(request, "Successfully advanced student.")
			# uncomment the below if you want to load the portal again
			# return HttpResponseRedirect(reverse("portal", args=(student_id,)))
	else:
		form = forms.AdvanceForm(instance = student)

	context = {'title' : "Advance " + student.name}
	context['form'] = form
	context['student'] = student
	context['omniscient'] = student.is_taught_by(request.user)
	context['curriculum'] = student.generate_curriculum_rows(
			omniscient = context['omniscient'])
	context['num_psets'] = student.uploadedfile_set.filter(category='psets')\
			.values('unit').distinct().count()
	return render(request, "roster/advance.html", context)


def get_checksum(student):
	key = settings.INVOICE_HASH_KEY
	return pbkdf2_hmac('sha256',
			(key+str(student.id)+student.user.username+'meow').encode('utf-8'),
			b'salt is yummy so is sugar', 100000, dklen = 18).hex()

@login_required
def invoice(request, student_id=None):
	if student_id is None:
		student = infer_student(request)
		return HttpResponseRedirect(
				reverse("invoice", args=(student.id,)))

	# Now assume student_id is not None
	student = get_student_by_id(request, student_id, payment_exempt = True)

	if not student.semester.show_invoices:
		invoice = None
	else:
		try:
			invoice = student.invoice
		except ObjectDoesNotExist:
			invoice = None

	context = {'title' : "Invoice for " + student.name,
			'student' : student, 'invoice' : invoice,
			'checksum' : get_checksum(student)}
	# return HttpResponse("hi")
	return render(request, "roster/invoice.html", context)

# this is not gated
def invoice_standalone(request, student_id, checksum):
	student = models.Student.objects.get(id=student_id)
	if checksum != get_checksum(student):
		raise HttpResponseBadRequest("Bad hash provided")
	try:
		invoice = student.invoice
	except ObjectDoesNotExist:
		raise Http404("No invoice exists for this student")
	context = {'title' : "Invoice for " + student.name,
			'student' : student, 'invoice' : invoice, 'checksum' : checksum}
	# return HttpResponse("hi")
	return render(request, "roster/invoice-standalone.html", context)


@staff_member_required
def master_schedule(request):
	student_names_and_unit_ids = get_current_students().filter(legit=True)\
			.values('user__first_name', 'user__last_name', 'curriculum')
	unit_to_student_names = collections.defaultdict(list)
	for d in student_names_and_unit_ids:
		# e.g. d = {'name' : Student, 'curriculum' : 30}
		unit_to_student_names[d['curriculum']].append(
				d['user__first_name'] + ' ' + d['user__last_name'])

	chart = collections.OrderedDict() # ordered dict(unit -> students)
	units = core.models.Unit.objects.order_by('position')
	for unit in units:
		chart[unit] = unit_to_student_names[unit.id]
	semester = core.models.Semester.objects.get(active=True)
	context = {
			'chart' : chart,
			'title' : "Master Schedule",
			'semester' : semester}
	return render(request, "roster/master-schedule.html", context)

class UpdateInvoice(PermissionRequiredMixin, UpdateView):
	permission_required = 'is_staff'
	model = models.Invoice
	fields = ('preps_taught', 'hours_taught',
			'adjustment', 'extras', 'total_paid', 'forgive',)
	object : models.Invoice

	def get_success_url(self):
		return reverse("invoice", args=(self.object.student.id,))

# Inquiry views
@login_required
def inquiry(request, student_id):
	student = get_student_by_id(request, student_id)
	if not student.semester.active:
		raise PermissionDenied("Not an active semester")
	if student.newborn:
		raise PermissionDenied("This form isn't enabled yet.")
	context = {}
	context['title'] = 'Unit Inquiry'
	current_inquiries = models.UnitInquiry.objects.filter(student=student)

	# Create form for submitting new inquiries
	if request.method == 'POST':
		form = forms.InquiryForm(request.POST)
		if form.is_valid():
			inquiry = form.save(commit=False)
			inquiry.student = student
			# check if exists already and created recently
			one_day_ago = timezone.now() - datetime.timedelta(seconds=90)
			if models.UnitInquiry.objects.filter(unit=inquiry.unit, \
					student=student, action_type=inquiry.action_type, \
					created_at__gte = one_day_ago).exists():
				messages.warning(request, "The same inquiry already was "\
						"submitted within the last 90 seconds.")
			else:
				inquiry.save()
				# auto-acceptance criteria
				auto_accept_criteria = (inquiry.action_type == "APPEND") \
						or (inquiry.action_type == "DROP") \
						or current_inquiries.filter(action_type="UNLOCK").count() <= 3 \
						or request.user.is_staff
				# auto reject criteria
				auto_reject_criteria = inquiry.action_type == "UNLOCK" and \
						(current_inquiries.filter(action_type="UNLOCK", status="NEW").count()
						+ student.unlocked_units.count()) > 9

				if auto_accept_criteria:
					inquiry.run_accept()
					messages.success(request, "Inquiry automatically approved.")
				elif auto_reject_criteria:
					inquiry.status = "REJ"
					inquiry.save()
					messages.error(request,
							"You can't have more than 9 unfinished units unlocked at once.")
				else:
					messages.success(request, "Inquiry submitted, should be approved soon!")
	else:
		form = forms.InquiryForm()
	context['form'] = form

	context['inquiries'] = models.UnitInquiry.objects\
			.filter(student=student)
	context['student'] = student
	context['curriculum'] = student.generate_curriculum_rows(
			omniscient = can_edit(request, student))

	return render(request, 'roster/inquiry.html', context)

class ListInquiries(PermissionRequiredMixin, ListView):
	permission_required = 'is_staff'
	model = models.UnitInquiry
	def get_queryset(self):
		queryset = models.UnitInquiry.objects\
				.filter(created_at__gte = timezone.now() - datetime.timedelta(days=7))\
				.filter(student__semester__active = True)\
				.exclude(status="ACC")

		# some amazing code vv
		count_unlock = models.UnitInquiry.objects\
				.filter(action_type="UNLOCK")\
				.filter(student=OuterRef('student'))\
				.order_by().values('student')\
				.annotate(c=Count('*')).values('c')
		count_all = models.UnitInquiry.objects\
				.filter(student=OuterRef('student'))\
				.order_by().values('student')\
				.annotate(c=Count('*')).values('c')
		# seriously wtf
		return queryset.annotate(
				num_unlock = Subquery(count_unlock,
					output_field=IntegerField()),
				num_all = Subquery(count_all,
					output_field=IntegerField()))

class EditInquiry(PermissionRequiredMixin, UpdateView):
	fields = ('unit', 'action_type', 'status', 'explanation')
	permission_required = 'is_staff'
	model = models.UnitInquiry
	object: models.UnitInquiry
	def get_success_url(self):
		return reverse("edit-inquiry", args=(self.object.pk,)) # typing: ignore

@staff_member_required
def approve_inquiry(_ : HttpRequest, pk) -> HttpResponse:
	inquiry = models.UnitInquiry.objects.get(id=pk)
	inquiry.run_accept()
	return HttpResponseRedirect(reverse("inquiry", args=(inquiry.student.id,)))

@staff_member_required
def approve_inquiry_all(_ : HttpRequest) -> HttpResponse:
	for inquiry in models.UnitInquiry.objects\
			.filter(status="NEW", student__semester__active = True):
		inquiry.run_accept()
	return HttpResponseRedirect(reverse("list-inquiry"))

@login_required
def register(request : HttpRequest) -> HttpResponse:
	try:
		container = models.RegistrationContainer.objects.get(semester__active = True)
	except:
		return HttpResponse("There isn't a currently active OTIS semester.", status = 503)

	semester : core.models.Semester = container.semester
	assert isinstance(request.user, User)
	if models.StudentRegistration.objects.filter(
			user = request.user,
			container = container
			).exists():
		messages.info(request,
				message = "You have already submitted a decision form for this year!")
		form = None
	elif request.method == 'POST':
		form = forms.DecisionForm(request.POST, request.FILES)
		if form.is_valid():
			passcode = form.cleaned_data['passcode']
			if passcode.lower() != container.passcode.lower():
				messages.error(request,
						message = "Wrong passcode")
			elif form.cleaned_data['track'] not in container.allowed_tracks.split(','):
				messages.error(request,
						message = "That track is not currently accepting registrations.")
			else:
				registration = form.save(commit = False)
				registration.container = container
				registration.user = request.user
				registration.save()
				messages.success(request, message = "Submitted! Sit tight.")
				return HttpResponseRedirect(reverse("index"))
	else:
		if container.allowed_tracks:
			initial_data_dict = {}
			most_recent_reg = models.StudentRegistration.objects\
					.filter(user = request.user).order_by('-id').first()
			if most_recent_reg is not None:
				for k in ('parent_email', 'graduation_year', 'school_name', 'aops_username', 'gender'):
					initial_data_dict[k] = getattr(most_recent_reg, k)
			form = forms.DecisionForm(initial = initial_data_dict)
		else:
			messages.warning(request, message = "The currently active semester isn't accepting registrations right now.")
			form = None
	context = {'title' : f'{semester} Decision Form', 'form' : form, 'container' : container}
	return render(request, 'roster/decision_form.html', context)

@csrf_exempt
@require_POST
def api(request):
	if settings.PRODUCTION:
		token = request.POST.get('token')
		if not sha256(token.encode('ascii')).hexdigest() == settings.API_TARGET_HASH:
			return JsonResponse({'error' : "☕"}, status = 418)
	# check whether social account exists
	uid = int(request.POST.get('uid'))
	queryset = SocialAccount.objects.filter(uid = uid)
	if not (n := len(queryset)) == 1:
		return JsonResponse({'result' : 'nonexistent', 'length' : n})

	social = queryset.get() # get the social account for this; should never 404
	user = social.user
	student = models.Student.objects.filter(user = user, semester__active = True).first()
	regform = models.StudentRegistration.objects.filter(user = user, container__semester__active = True).first()

	if student is not None:
		return JsonResponse({
			'result' : 'success',
			'user' : social.user.username,
			'name': social.user.get_full_name(),
			'uid' : uid,
			'track' : student.track,
			'gender' : regform.gender if regform is not None else '?',
			'country': regform.country if regform is not None else '???',
			'num_years' : models.Student.objects.filter(user = user).count(),
			})
	elif student is None and regform is not None:
		return JsonResponse({ 'result' : 'pending' })
	else:
		return JsonResponse({ 'result' : 'unregistered' })
