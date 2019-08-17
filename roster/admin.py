from django.contrib import admin, auth
from import_export import resources, widgets, fields
from import_export.admin import ImportExportModelAdmin

import core
import roster

# Register your models here.

class StudentInline(admin.TabularInline):
	model = roster.models.Student
	fields = ('user', 'name', 'semester', 'track', 'legit', 'current_unit_index',)
	readonly_fields = ('user', 'name', 'semester',)
	extra = 0

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

## ASSISTANT
class AssistantIEResource(RosterResource):
	class Meta:
		skip_unchanged = True
		model = roster.models.Assistant
		fields = ('id', 'user_name', 'shortname', 'user__first_name', 'user__last_name',)

@admin.register(roster.models.Assistant)
class AssistantAdmin(ImportExportModelAdmin):
		list_display = ('id', 'name', 'user', 'shortname')
		inlines = (StudentInline,)
		resource_class = AssistantIEResource

## INVOICE
class InvoiceIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = roster.models.Invoice
		fields = ('id', 'student', 'student__user__first_name', 'student__user__last_name', 'student__track',
				'preps_taught', 'hours_taught', 'total_paid', 'student__semester__name',)

class InvoiceInline(admin.StackedInline):
	model = roster.models.Invoice
	fields = ('preps_taught', 'hours_taught', 'total_paid',)
	readonly_fields = ('student', 'id',)

@admin.register(roster.models.Invoice)
class InvoiceAdmin(ImportExportModelAdmin):
	list_display = ('student', 'track', 'total_owed', 'total_paid', 'total_cost', 'updated_at',)
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

@admin.register(roster.models.Student)
class StudentAdmin(ImportExportModelAdmin):
	list_display = ('name', 'user', 'id', 'semester', 'assistant', 'legit', 'track', 'current_unit_index', 'curriculum_length',)
	list_filter = ('semester__active', 'legit', 'semester', 'track',)
	resource_class = StudentIEResource
	inlines = (InvoiceInline,)
	search_fields = ('user__first_name', 'user__last_name', 'user__username',)
