from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseRedirect, Http404
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.views.generic.edit import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin

import itertools
import collections

import core
import roster, roster.utils
from . import forms

# Create your views here.

@login_required
def curriculum(request, student_id):
	student = get_object_or_404(roster.models.Student.objects, id = student_id)
	roster.utils.check_taught_by(request, student)
	units = core.models.Unit.objects.all()
	original = student.curriculum.values_list('id', flat=True)

	if request.method == 'POST' and request.user.is_staff:
		form = forms.CurriculumForm(request.POST, units = units, enabled = True)
		if form.is_valid():
			data = form.cleaned_data
			values = [data[k] for k in data if k.startswith('group-') and data[k] is not None]
			student.curriculum = values
			student.save()
			messages.success(request, "Successfully saved curriculum of %d units." % len(values))
	elif request.user.is_staff: # staff can edit
		form = forms.CurriculumForm(units = units, original = original, enabled = True)
	else: # otherwise can only read
		form = forms.CurriculumForm(units = units, original = original)
		messages.info(request, "You can't edit this curriculum since you are not a staff member.")

	context = {'title' : "Curriculum for " + student.name,
			'student' : student, 'form' : form}
	# return HttpResponse("hi")
	return render(request, "roster/currshow.html", context)

@login_required
def advance(request, student_id):
	student = get_object_or_404(roster.models.Student.objects, id = student_id)
	roster.utils.check_taught_by(request, student)
	
	if request.method == 'POST':
		form = forms.AdvanceForm(request.POST, instance = student)
		if form.is_valid():
			form.save()
			messages.success(request, "Successfully advanced student.")
			# uncomment the below if you want to load the dashboard again
			# return HttpResponseRedirect(reverse("dashboard", args=(student_id,)))
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
		try:
			student = roster.models.Student.objects.get(
					semester__active = True, user = request.user)
		except(roster.models.Student.MultipleObjectsReturned,
				roster.models.Student.DoesNotExist):
			raise Http404("No such student")
		else:
			return HttpResponseRedirect(reverse("invoice", args=(student.id,)))
	# Now assume student_id is not None
	student = get_object_or_404(roster.models.Student.objects, id = student_id)
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
	student_names_and_unit_ids = roster.models.Student.objects\
			.filter(semester__active=True, legit=True)\
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

class UpdateInvoice(LoginRequiredMixin, UpdateView):
	model = roster.models.Invoice
	fields = ('preps_taught', 'hours_taught', 'total_paid',)

	def get_success_url(self):
		return reverse("invoice", args=(self.object.student.id,))

	def get_object(self, *args, **kwargs):
		if not self.request.user.is_staff:
			raise Http404("Not authorized to update this invoice")
		return super(UpdateInvoice, self).get_object(*args, **kwargs)
