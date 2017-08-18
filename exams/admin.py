from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

import exams

# Register your models here.

class MockOlympiadIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = exams.models.MockOlympiad
		fields = ('id', 'family', 'number', 'jmo_url', 'usamo_url', 'solns_url', 'due_date',)

@admin.register(exams.models.MockOlympiad)
class MockOlympiadAdmin(ImportExportModelAdmin):
	list_display = ('family', 'number', 'due_date',)
	search_fields = ('family', 'number',)
	resource_class = MockOlympiadIEResource

class AssignmentIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = exams.models.Assignment
		fields = ('id', 'name', 'due_date',)

@admin.register(exams.models.Assignment)
class AssignmentAdmin(ImportExportModelAdmin):
	list_display = ('id', 'name', 'due_date',)
	search_fields = ('name',)
	resource_class = AssignmentIEResource
