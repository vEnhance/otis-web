from typing import List, Tuple

from core.models import Semester, Unit
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.db.models import F, FloatField, QuerySet
from django.db.models.base import Model
from django.db.models.functions import Cast
from django.http import HttpRequest
from import_export import fields, resources, widgets
from import_export.admin import ImportExportModelAdmin

from .models import Assistant, Invoice, RegistrationContainer, Student, StudentRegistration, UnitInquiry  # NOQA


class RosterResource(resources.ModelResource):
	user_name = fields.Field(
		column_name='User Name',
		attribute='user',
		widget=widgets.ForeignKeyWidget(User, 'username')
	)


# ASSISTANT
class AssistantIEResource(RosterResource):
	class Meta:
		skip_unchanged = True
		model = Assistant
		fields = (
			'id',
			'user_name',
			'shortname',
			'user__first_name',
			'user__last_name',
		)


class StudentInline(admin.TabularInline):
	model = Student  # type: ignore
	fk_name = "assistant"
	fields = (
		'name',
		'semester',
		'track',
		'legit',
	)
	readonly_fields = (
		'user',
		'name',
		'semester',
	)
	extra = 0
	show_change_link = True

	def has_delete_permission(self, request: HttpRequest, obj: Student = None) -> bool:
		return False


@admin.register(Assistant)
class AssistantAdmin(ImportExportModelAdmin):
	list_display = (
		'id',
		'name',
		'shortname',
		'user',
	)
	list_display_links = ('name', )
	search_fields = ('user__first_name', 'user__last_name', 'user__username')
	autocomplete_fields = (
		'user',
		'unlisted_students',
	)
	inlines = (StudentInline, )
	resource_class = AssistantIEResource


# INVOICE
class InvoiceIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = Invoice
		fields = (
			'id',
			'student',
			'student__track',
			'student__user__first_name',
			'student__user__last_name',
			'student__user__email',
			'preps_taught',
			'hours_taught',
			'adjustment',
			'extras',
			'total_paid',
			'student__semester__name',
			'forgive',
			'memo',
		)


class OwedFilter(admin.SimpleListFilter):
	title = 'remaining balance'
	parameter_name = 'has_owed'

	def lookups(self, request: HttpRequest, model_admin: 'InvoiceAdmin') -> List[Tuple[str, str]]:
		return [
			("incomplete", "Incomplete"), ("paid", "Paid in full"), ("excess", "Overpaid"),
			("zero", "No payment")
		]

	def queryset(self, request: HttpRequest, queryset: QuerySet[Model]):
		if self.value() is None:
			return queryset
		else:
			queryset = queryset.annotate(
				owed=Cast(
					F("student__semester__prep_rate") * F("preps_taught") +
					F("student__semester__hour_rate") * F("hours_taught") + F("adjustment") +
					F('extras') - F("total_paid"), FloatField()
				)
			)
			if self.value() == "incomplete":
				return queryset.filter(owed__gt=0)
			elif self.value() == "paid":
				return queryset.filter(owed__lte=0)
			elif self.value() == "excess":
				return queryset.filter(owed__lt=0)
			elif self.value() == "zero":
				return queryset.filter(owed__gt=0).filter(total_paid=0)


@admin.register(Invoice)
class InvoiceAdmin(ImportExportModelAdmin):
	list_display = (
		'student',
		'track',
		'total_owed',
		'total_cost',
		'forgive',
	)
	list_display_links = ('student', )
	search_fields = (
		'student__user__first_name',
		'student__user__last_name',
	)
	autocomplete_fields = ('student', )
	ordering = ('student', )
	list_filter = (
		OwedFilter,
		'student__legit',
		'student__semester__active',
		'student__track',
		'forgive',
		'student__semester',
	)
	resource_class = InvoiceIEResource


# STUDENT
class StudentIEResource(RosterResource):
	semester_name = fields.Field(
		column_name='Semester Name',
		attribute='semester',
		widget=widgets.ForeignKeyWidget(Semester, 'name')
	)
	unit_list = fields.Field(
		column_name='Unit List',
		attribute='curriculum',
		widget=widgets.ManyToManyWidget(Unit, separator=';')
	)

	class Meta:
		skip_unchanged = True
		model = Student
		fields = (
			'id',
			'user__first_name',
			'user__last_name',
			'user__email',
			'semester_name',
			'user_name',
			'track',
			'legit',
		)
		export_order = fields


class UnlistedInline(admin.TabularInline):
	model = Student.unlisted_assistants.through  # type: ignore
	verbose_name = "Unlisted Assistant"
	verbose_name_plural = "Unlisted Assistants"
	extra = 0


class InvoiceInline(admin.StackedInline):
	model = Invoice  # type: ignore
	fields = (
		'preps_taught',
		'hours_taught',
		'extras',
		'adjustment',
		'total_paid',
		'forgive',
		'memo',
	)
	readonly_fields = (
		'student',
		'id',
	)


@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin):
	list_display = (
		'name',
		'user',
		'id',
		'semester',
		'legit',
		'track',
	)
	list_filter = (
		'assistant',
		'semester__active',
		'semester',
		'legit',
		'track',
		'newborn',
	)
	search_fields = (
		'user__first_name',
		'user__last_name',
		'user__username',
	)
	autocomplete_fields = (
		'user',
		'curriculum',
		'unlocked_units',
	)
	inlines = (
		InvoiceInline,
		UnlistedInline,
	)
	resource_class = StudentIEResource


# REG FORM
class StudentRegistrationIEResource(RosterResource):
	class Meta:
		model = StudentRegistration
		fields = (
			'id',
			'user__first_name',
			'user__last_name',
			'user__email',
			'user_name',
			'container__semester__name',
			'processed',
			'parent_email',
			'track',
			'country',
			'gender',
			'graduation_year',
			'school_name',
			'aops_username',
		)
		export_order = fields


def build_students(queryset: QuerySet[StudentRegistration]) -> int:
	students_to_create = []
	invoices_to_create = []
	queryset = queryset.filter(container__semester__active=True)
	queryset = queryset.exclude(processed=True)
	queryset = queryset.select_related('user', 'container', 'container__semester')

	count = 0
	n = 0
	for registration in queryset:
		students_to_create.append(
			Student(
				user=registration.user,
				semester=registration.container.semester,
				track=registration.track,
			)
		)
		n = registration.container.num_preps
		count += 1
	Student.objects.bulk_create(students_to_create)
	queryset.update(processed=True)

	if n > 0:
		for student in Student.objects.filter(invoice__isnull=True, semester__active=True):
			if student.track == "A":
				hours_taught = 8.4 * n
			elif student.track == "B":
				hours_taught = 4.2 * n
			else:
				hours_taught = 0
			invoice = Invoice(student=student, preps_taught=n, hours_taught=hours_taught)
			invoices_to_create.append(invoice)
		Invoice.objects.bulk_create(invoices_to_create)
	return count


@admin.register(StudentRegistration)
class StudentRegistrationAdmin(ImportExportModelAdmin):
	list_display = (
		'container',
		'processed',
		'name',
		'track',
		'about',
		'agreement_form',
	)
	list_filter = (
		'container__semester',
		'processed',
		'track',
		'gender',
		'graduation_year',
	)
	list_display_links = (
		'name',
		'track',
	)
	resource_class = StudentRegistrationIEResource
	search_fields = ('user__first_name', 'user__last_name')

	actions = [
		'create_student',
	]

	def create_student(self, request: HttpRequest, queryset: QuerySet[StudentRegistration]):
		num_built = build_students(queryset)
		messages.success(request, message=f"Built {num_built} students")


# INQUIRY
@admin.register(UnitInquiry)
class UnitInquiryAdmin(admin.ModelAdmin):
	list_display = (
		'id',
		'status',
		'action_type',
		'unit',
		'student',
		'explanation',
	)
	list_filter = (
		'status',
		'action_type',
		'student__assistant',
	)
	search_fields = (
		'student__user__first_name',
		'student__user__last_name',
		'student__user__username',
	)
	list_display_links = ('id', )
	autocomplete_fields = (
		'unit',
		'student',
	)

	actions = ['hold_inquiry', 'reject_inquiry', 'accept_inquiry', 'reset_inquiry']

	def hold_inquiry(self, request: HttpRequest, queryset: QuerySet[UnitInquiry]):
		queryset.update(status='HOLD')

	def reject_inquiry(self, request: HttpRequest, queryset: QuerySet[UnitInquiry]):
		queryset.update(status='REJ')

	def accept_inquiry(self, request: HttpRequest, queryset: QuerySet[UnitInquiry]):
		for inquiry in queryset:
			inquiry.run_accept()

	def reset_inquiry(self, request: HttpRequest, queryset: QuerySet[UnitInquiry]):
		queryset.update(status='NEW')


# REGISTRATION
@admin.register(RegistrationContainer)
class RegistrationContainerAdmin(admin.ModelAdmin):
	list_display = (
		'id',
		'semester',
		'passcode',
		'allowed_tracks',
	)
	list_display_links = (
		'id',
		'semester',
	)
