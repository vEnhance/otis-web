from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

import core
import exams

# Register your models here.

class SemesterResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = core.models.Semester
		fields = ('id', 'name', 'active', 'show_invoices',)

@admin.register(core.models.Semester)
class SemesterAdmin(ImportExportModelAdmin):
	list_display = ('name', 'id', 'active', 'show_invoices',)
	search_fields = ('name',)
	resource_class = SemesterResource

class UnitIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = core.models.Unit
		fields = ('id', 'name', 'code', 'subject', 'prob_url', 'soln_url', 'position')

@admin.register(core.models.Unit)
class UnitAdmin(ImportExportModelAdmin):
	list_display = ('name', 'code', 'subject', 'position',)
	search_fields = ('name', 'code')
	ordering = ('position',)
	resource_class = UnitIEResource
	list_per_page = 150
	list_max_show_all = 400

