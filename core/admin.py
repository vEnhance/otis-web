from django.contrib import admin
from import_export import resources, widgets, fields
from import_export.admin import ImportExportModelAdmin

import core

# Register your models here.

@admin.register(core.models.Semester)
class SemesterAdmin(admin.ModelAdmin):
	list_display = ('name', 'active')
	search_fields = ('name',)
@admin.register(core.models.Handout)
class HandoutAdmin(admin.ModelAdmin):
	list_display = ('position', 'name', 'code')
	search_fields = ('name', 'code')
