from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

import core
import exams

# Register your models here.

class AssignmentInline(admin.TabularInline):
	model = exams.models.Assignment
	fields = ('name', 'olympiad', 'due_date',)
	extra = 0

@admin.register(core.models.Semester)
class SemesterAdmin(admin.ModelAdmin):
	list_display = ('name', 'active',)
	search_fields = ('name',)
	inlines = (AssignmentInline,)


class UnitIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = core.models.Unit
		fields = ('id', 'name', 'code', 'prob_url', 'soln_url', 'position')

@admin.register(core.models.Unit)
class UnitAdmin(ImportExportModelAdmin):
	list_display = ('name', 'code', 'position',)
	search_fields = ('name', 'code')
	ordering = ('position',)
	resource_class = UnitIEResource
