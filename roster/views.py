"""Roster views

For historical reasons (aka I didn't plan ahead),
the division between dashboard and roster is a bit weird.

* roster handles the list of students and their curriculums
* roster also handles invoices
* dashboard handles stuff and uploads and pset submissions

So e.g. "list students by most recent pset" goes under dashboard.
"""

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.views.generic.edit import UpdateView
from django.views.generic import ListView
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Subquery, OuterRef, Count, IntegerField

from django.utils import timezone
import datetime
import itertools
import collections
from hashlib import pbkdf2_hmac

import os
import core
from . import models
from . import forms
from . import utils

# Create your views here.

@login_required
def curriculum(request, student_id):
	student = utils.get_student(student_id)
	utils.check_can_view(request, student)
	units = core.models.Unit.objects.all()
	original = student.curriculum.values_list('id', flat=True)

	enabled = student.is_taught_by(request.user) or student.newborn
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
def finalize(request, student_id):
	# Removes a newborn status, thus activating everything
	student = utils.get_student(student_id)
	utils.check_can_view(request, student)
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
	student = utils.get_student(student_id)
	utils.check_taught_by(request, student)
	unit = core.models.Unit.objects.get(id=unit_id)

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
		target = core.models.Unit.objects.get(id=target_id)
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
	student = utils.get_student(student_id)
	utils.check_taught_by(request, student)
	
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
	key = os.getenv("INVOICE_HASH_KEY", "evan_chen_is_still_really_cool")
	return pbkdf2_hmac('sha256',
			(key+str(student.id)+student.user.username+'meow').encode('utf-8'),
			b'salt is yummy so is sugar', 100000, dklen = 18).hex()

@login_required
def invoice(request, student_id=None):
	if student_id is None:
		student = utils.infer_student(request)
		return HttpResponseRedirect(
				reverse("invoice", args=(student.id,)))

	# Now assume student_id is not None
	student = utils.get_student(student_id)
	if student.user != request.user and not request.user.is_staff:
		raise PermissionDenied("Can't view invoice")

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

def invoice_standalone(request, student_id, checksum):
	# Now assume student_id is not None
	student = utils.get_student(student_id)

	if checksum != get_checksum(student):
		raise PermissionDenied("Bad hash provided")

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
	student_names_and_unit_ids = utils\
			.get_current_students().filter(legit=True)\
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
	fields = ('preps_taught', 'hours_taught', 'adjustment', 'extras', 'total_paid',)

	def get_success_url(self):
		return reverse("invoice", args=(self.object.student.id,))

# Inquiry views
def inquiry(request, student_id):
	student = utils.get_student(student_id)
	utils.check_can_view(request, student)
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
			omniscient = student.is_taught_by(request.user))

	return render(request, 'roster/inquiry.html', context)

class ListInquiries(PermissionRequiredMixin, ListView):
	permission_required = 'is_staff'
	model = models.UnitInquiry
	def get_queryset(self):
		queryset = models.UnitInquiry.objects\
				.filter(created_at__gte = timezone.now() - datetime.timedelta(days=7))\
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
	def get_success_url(self):
		return reverse("edit-inquiry", args=(self.object.id,))

@staff_member_required
def approve_inquiry(request, pk):
	inquiry = models.UnitInquiry.objects.get(id=pk)
	inquiry.run_accept()
	return HttpResponseRedirect(reverse("inquiry", args=(inquiry.student.id,)))

@staff_member_required
def approve_inquiry_all(request):
	for inquiry in models.UnitInquiry.objects.filter(status="NEW"):
		inquiry.run_accept()
	return HttpResponseRedirect(reverse("list-inquiry"))

def delinquent(self, student_id):
	raise NotImplementedError("WIP")
