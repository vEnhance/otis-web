from django.contrib import admin, auth, messages
from django.db.models import F, FloatField, QuerySet
from django.db.models.functions import Cast
from django.http import HttpRequest
from import_export import resources, widgets, fields
from import_export.admin import ImportExportModelAdmin

import core, core.models
import roster, roster.models

class RosterResource(resources.ModelResource):
	user_name = fields.Field(column_name = 'User Name',
			attribute = 'user',
			widget = widgets.ForeignKeyWidget(auth.models.User, 'username'))
	semester_name = fields.Field(column_name = 'Semester Name',
			attribute = 'semester',
			widget = widgets.ForeignKeyWidget(core.models.Semester, 'name'))
	unit_list = fields.Field(column_name = 'Unit List',
			attribute = 'curriculum',
			widget = widgets.ManyToManyWidget(core.models.Unit, separator=';'))


# Register your models here.

## ASSISTANT
class AssistantIEResource(RosterResource):
	class Meta:
		skip_unchanged = True
		model = roster.models.Assistant
		fields = ('id', 'user_name', 'shortname', 'user__first_name', 'user__last_name',)
class StudentInline(admin.TabularInline):
	model = roster.models.Student
	fk_name = "assistant"
	fields = ('name', 'semester', 'track', 'legit', 'num_units_done',)
	readonly_fields = ('user', 'name', 'semester',)
	extra = 0
	show_change_link = True
	def has_delete_permission(self, request : HttpRequest, obj=None):
		return False
@admin.register(roster.models.Assistant)
class AssistantAdmin(ImportExportModelAdmin):
		list_display = ('id', 'name', 'shortname', 'user',)
		list_display_links = ('name',)
		search_fields = ('user__first_name', 'user__last_name', 'user__username')
		autocomplete_fields = ('user', 'unlisted_students',)
		inlines = (StudentInline,)
		resource_class = AssistantIEResource

## INVOICE
class InvoiceIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = roster.models.Invoice
		fields = ('id', 'student','student__track',
				'student__user__first_name', 'student__user__last_name',
				'preps_taught', 'hours_taught', 'adjustment', 'extras',
				'total_paid', 'student__semester__name',)
class OwedFilter(admin.SimpleListFilter):
	title = 'remaining balance'
	parameter_name = 'has_owed'

	def lookups(self, request : HttpRequest, model_admin):
		return [("incomplete", "Incomplete"), ("paid", "Paid in full"), ("zero", "No payment")]
	def queryset(self, request : HttpRequest, queryset : QuerySet):
		if self.value() is None:
			return queryset
		else:
			queryset = queryset.annotate(owed =
					Cast(F("student__semester__prep_rate") * F("preps_taught")
					+ F("student__semester__hour_rate") * F("hours_taught")
					+ F("adjustment") + F('extras') - F("total_paid"), FloatField()))
			if self.value() == "incomplete":
				return queryset.filter(owed__gt=0)
			elif self.value() == "paid":
				return queryset.filter(owed__lte=0)
			elif self.value() == "zero":
				return queryset.filter(owed__gt=0).filter(total_paid=0)

@admin.register(roster.models.Invoice)
class InvoiceAdmin(ImportExportModelAdmin):
	list_display = ('student', 'track', 'total_owed', 'total_paid', 'total_cost', 'updated_at', 'forgive',)
	list_display_links = ('student',)
	search_fields = ('student__user__first_name', 'student__user__last_name',)
	autocomplete_fields = ('student',)
	ordering = ('student',)
	list_filter = (OwedFilter, 'student__semester__active', 'student__semester', 'student__legit', 'student__track',)
	resource_class = InvoiceIEResource

## STUDENT
class StudentIEResource(RosterResource):
	class Meta:
		skip_unchanged = True
		model = roster.models.Student
		fields = ('id', 'user__first_name', 'user__last_name', 'semester_name',
				'user_name', 'track', 'legit', 'email', 'parent_email')
		export_order = ('id', 'user__first_name', 'user__last_name', 'semester_name',
				'user_name', 'track', 'legit', 'email', 'parent_email')
class UnlistedInline(admin.TabularInline):
	model = roster.models.Student.unlisted_assistants.through
	verbose_name = "Unlisted Assistant"
	verbose_name_plural = "Unlisted Assistants"
	extra = 0
class InvoiceInline(admin.StackedInline):
	model = roster.models.Invoice
	fields = ('preps_taught', 'hours_taught', 'extras', 'adjustment', 'total_paid', 'forgive',)
	readonly_fields = ('student', 'id',)
@admin.register(roster.models.Student)
class StudentAdmin(ImportExportModelAdmin):
	list_display = ('name', 'user', 'id', 'semester', 'legit', 'track', 'num_units_done', 'curriculum_length',)
	list_filter = ('semester__active', 'legit', 'semester', 'track', 'newborn',)
	search_fields = ('user__first_name', 'user__last_name', 'user__username',)
	autocomplete_fields = ('user', 'curriculum', 'unlocked_units',)
	inlines = (InvoiceInline, UnlistedInline,)
	resource_class = StudentIEResource

## INQUIRY
@admin.register(roster.models.UnitInquiry)
class UnitInquiryAdmin(admin.ModelAdmin):
	list_display = ('id', 'status', 'action_type',
			'unit', 'student', 'explanation',)
	list_filter = ('status', 'action_type',)
	search_fields = ('student__user__first_name',
			'student__user__last_name', 'student__user__username')
	list_display_links = ('id',)
	autocomplete_fields = ('unit', 'student',)

	actions = ['hold_inquiry', 'reject_inquiry', 'accept_inquiry', 'reset_inquiry']

	def hold_inquiry(self, request: HttpRequest, queryset: QuerySet):
		queryset.update(status='HOLD')
	def reject_inquiry(self, request: HttpRequest, queryset: QuerySet):
		queryset.update(status='REJ')
	def accept_inquiry(self, request: HttpRequest, queryset: QuerySet):
		queryset.update(status='ACC')
	def reset_inquiry(self, request: HttpRequest, queryset: QuerySet):
		queryset.update(status='NEW')

## REGISTRATION
@admin.register(roster.models.RegistrationContainer)
class RegistrationContainerAdmin(admin.ModelAdmin):
	list_display = ('id', 'semester', 'passcode', 'allowed_tracks',)
	list_display_links = ('id', 'semester',)

# TODO later make this import export able
@admin.register(roster.models.StudentRegistration)
class StudentRegistrationAdmin(admin.ModelAdmin):
	list_display = ('processed', 'name', 'track', 'about', 'country', 'aops_username', 'agreement_form',)
	list_filter = ('processed', 'track', 'gender', 'graduation_year',)
	list_display_links = ('track',)

	actions = ['create_student',]
	def create_student(self, request : HttpRequest, queryset : QuerySet):
		students_to_create = []
		queryset = queryset.exclude(processed=True)
		queryset.select_related('user', 'container', 'container__semester')
		for registration in queryset:
			students_to_create.append(roster.models.Student(
					user = registration.user,
					semester = registration.container.semester,
					track = registration.track,
					))
			registration.user.save()
		messages.success(request, message=f"Built {len(students_to_create)} students")
		roster.models.Student.objects.bulk_create(students_to_create)
		queryset.update(processed=True)

