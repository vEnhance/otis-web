from django.contrib import admin, auth
from import_export import resources, widgets, fields
from import_export.admin import ImportExportModelAdmin

import core
import roster

# Register your models here.

class StudentInline(admin.TabularInline):
	model = roster.models.Student
	fields = ('user', 'name', 'semester', 'legit', 'current_unit_index',)
	readonly_fields = ('user', 'name', 'semester',)
	extra = 0

class RosterResource(resources.ModelResource):
	user_name = fields.Field(column_name = 'User Name',
			attribute = 'user',
			widget = widgets.ForeignKeyWidget(auth.models.User, 'username'))
	semester_name = fields.Field(column_name = 'Semester Name',
			attribute = 'semester',
			widget = widgets.ForeignKeyWidget(core.models.Semester, 'name'))

class AssistantIEResource(RosterResource):
	class Meta:
		skip_unchanged = True
		model = roster.models.Assistant
		fields = ('id', 'name', 'semester_name', 'user_name',)

@admin.register(roster.models.Assistant)
class AssistantAdmin(ImportExportModelAdmin):
	list_display = ('name', 'semester', 'user', 'student_count',)
	inlines = (StudentInline,)
	list_filter = ('semester__active',)
	resource_class = AssistantIEResource

class StudentIEResource(RosterResource):
	class Meta:
		skip_unchanged = True
		model = roster.models.Student
		fields = ('id', 'name', 'semester_name', 'user_name', 'assistant', 'legit', 'current_unit_index', 'curriculum')

@admin.register(roster.models.Student)
class StudentAdmin(ImportExportModelAdmin):
	list_display = ('name', 'user', 'semester', 'assistant', 'legit', 'current_unit_index', 'curriculum_length',)
	ordering = ('semester', 'name', )
	list_filter = ('semester__active', 'legit',)
	resource_class = StudentIEResource

class InvoiceIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = roster.models.Invoice
		fields = ('student', 'preps_taught', 'hours_taught', 'amount_owed',
				'student__name', 'student__semester__name',)

@admin.register(roster.models.Invoice)
class InvoiceAdmin(ImportExportModelAdmin):
	list_display = ('student', 'cleared', 'amount_owed', 'total_cost', 'updated_at',)
	ordering = ('student',)
	list_filter = ('student__semester__active', 'student__semester',)
	resource_class = InvoiceIEResource
