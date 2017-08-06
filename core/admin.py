from django.contrib import admin
from import_export import resources, widgets, fields
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

@admin.register(core.models.Unit)
class UnitAdmin(admin.ModelAdmin):
	list_display = ('name', 'code', 'position',)
	search_fields = ('name', 'code')
	ordering = ('position',)
