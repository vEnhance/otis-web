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
from django.core.exceptions import ObjectDoesNotExist
from django.views.generic.edit import UpdateView
from django.views.generic import ListView
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Subquery, OuterRef, Count, IntegerField

import itertools
import collections

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

	enabled = student.is_taught_by(request.user)
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
					"Successfully saved curriculum of %d units." % len(values))
	else:
		form = forms.CurriculumForm(units = units,
				original = original, enabled = enabled)
		if not enabled:
			messages.info(request, "You can't edit this curriculum " \
					"since you are not an instructor.")

	context = {'title' : "Curriculum for " + student.name,
			'student' : student, 'form' : form, 'enabled' : enabled}
	# return HttpResponse("hi")
	return render(request, "roster/currshow.html", context)

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
	return render(request, "roster/advance.html", context)


@login_required
def invoice(request, student_id=None):
	if student_id is None:
		student = utils.infer_student(request)
		return HttpResponseRedirect(
				reverse("invoice", args=(student.id,)))

	# Now assume student_id is not None
	student = utils.get_student(student_id)
	if student.user != request.user and not request.user.is_staff:
		raise Http404("Can't view invoice")

	if not student.semester.show_invoices:
		invoice = None
	else:
		try:
			invoice = student.invoice
		except ObjectDoesNotExist:
			invoice = None

	context = {'title' : "Invoice for " + student.name,
			'student' : student, 'invoice' : invoice}
	# return HttpResponse("hi")
	return render(request, "roster/invoice.html", context)

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
	fields = ('preps_taught', 'hours_taught', 'total_paid',)

	def get_success_url(self):
		return reverse("invoice", args=(self.object.student.id,))

# Inquiry views
def inquiry(request, student_id):
	student = utils.get_student(student_id)
	utils.check_can_view(request, student)
	context = {}
	context['title'] = 'Unit Inquiry'

	# Create form for submitting new inquiries
	if request.method == 'POST':
		form = forms.InquiryForm(request.POST)
		if form.is_valid():
			inquiry = form.save(commit=False)
			inquiry.student = student
			inquiry.save()
			messages.success(request, "Request successful")
	else:
		form = forms.InquiryForm()
	context['form'] = form

	context['inquiries'] = models.UnitInquiry.objects\
			.filter(student=student)
	context['student'] = student
	context['curriculum'] = student.generate_curriculum_rows(
			omniscient = student.is_taught_by(request.user))

	return render(request, 'roster/inquiry.html', context)

class ListOpenInquiries(PermissionRequiredMixin, ListView):
	permission_required = 'is_staff'
	model = models.UnitInquiry
	def get_queryset(self):
		# some amazing code vv seriously wtf
		count_others = models.UnitInquiry.objects\
				.filter(student=OuterRef('student'))\
				.order_by().values('student')\
				.annotate(c=Count('*')).values('c')
		return models.UnitInquiry.objects\
				.filter(status='NEW')\
				.annotate(num_inq = Subquery(count_others,
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
	return HttpResponseRedirect(reverse("list-inquiry"))

@staff_member_required
def approve_inquiry_all(request):
	for inquiry in models.UnitInquiry.objects.filter(status="NEW"):
		inquiry.run_accept()
	return HttpResponseRedirect(reverse("list-inquiry"))
