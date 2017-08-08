from django.contrib import admin, auth
from import_export import resources, widgets, fields
from import_export.admin import ImportExportModelAdmin

import core
import roster

# Register your models here.

class ActiveFilter(admin.SimpleListFilter):
	title = "Current"
	parameter_name = 'type'
	def lookups(self, request, model_admin):
		return (("current", "Current"), ("past", "Past"),)
	def queryset(self, request, queryset):
		if self.value() is None:
			return queryset
		elif self.value() == "current":
			return queryset.filter(semester__active=True)
		elif self.value() == "past":
			return queryset.filter(semester__active=False)

class StudentInline(admin.TabularInline):
	model = roster.models.Student
	fields = ('user', 'name', 'semester', 'current_unit_index',)
	readonly_fields = ('user', 'name', 'semester',)
	extra = 0

class RosterResource(resources.ModelResource):
	user_name = fields.Field(column_name = 'User Name',
			attribute = 'user',
			widget = widgets.ForeignKeyWidget(auth.models.User, 'username'))
	semester_name = fields.Field(column_name = 'Semester Name',
			attribute = 'semester',
			widget = widgets.ForeignKeyWidget(core.models.Semester, 'name'))

class TAIEResource(RosterResource):
	class Meta:
		skip_unchanged = True
		model = roster.models.TA
		fields = ('id', 'name', 'semester_name', 'user_name',)

@admin.register(roster.models.TA)
class TAAdmin(ImportExportModelAdmin):
	list_display = ('name', 'semester', 'user', 'student_count',)
	inlines=(StudentInline,)
	list_filter=(ActiveFilter,)
	resource_class = TAIEResource

class StudentIEResource(RosterResource):
	class Meta:
		skip_unchanged = True
		model = roster.models.Student
		fields = ('id', 'name', 'semester_name', 'user_name', 'assistant', 'current_unit_index',)

@admin.register(roster.models.Student)
class StudentAdmin(ImportExportModelAdmin):
	list_display = ('name', 'user', 'semester', 'assistant', 'current_unit_index',)
	ordering = ('semester', 'name', )
	list_filter=(ActiveFilter,)
	resource_class = StudentIEResource
