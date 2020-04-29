from django.contrib import admin, auth
from import_export import resources, widgets, fields
from import_export.admin import ImportExportModelAdmin

import core
import roster

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
	def has_delete_permission(self, request, obj=None):
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
		fields = ('id', 'student', 'student__user__first_name', 'student__user__last_name', 'student__track',
				'preps_taught', 'hours_taught', 'total_paid', 'student__semester__name',)
@admin.register(roster.models.Invoice)
class InvoiceAdmin(ImportExportModelAdmin):
	list_display = ('student', 'track', 'total_owed', 'total_paid', 'total_cost', 'updated_at',)
	list_display_links = ('student',)
	search_fields = ('student__user__first_name', 'student__user__last_name',)
	autocomplete_fields = ('student',)
	ordering = ('student',)
	list_filter = ('student__semester__active', 'student__track', 'student__semester', 'student__legit')
	resource_class = InvoiceIEResource

## STUDENT
class StudentIEResource(RosterResource):
	class Meta:
		skip_unchanged = True
		model = roster.models.Student
		fields = ('id', 'user__first_name', 'user__last_name', 'semester_name',
				'user_name', 'assistant', 'track', 'legit', 'unit_list',)
		export_order = ('id', 'user__first_name', 'user__last_name', 'semester_name',
				'user_name', 'assistant', 'track', 'legit', 'unit_list',)
class UnlistedInline(admin.TabularInline):
	model = roster.models.Student.unlisted_assistants.through
	verbose_name = "Unlisted Assistant"
	verbose_name_plural = "Unlisted Assistants"
	extra = 0
class InvoiceInline(admin.StackedInline):
	model = roster.models.Invoice
	fields = ('preps_taught', 'hours_taught', 'total_paid',)
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
	list_filter = ('status',)
	search_fields = ('student__user__first_name',
			'student__user__last_name', 'student__user__username')
	list_display_links = ('id',)
	autocomplete_fields = ('unit', 'student',)
