from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

import exams

# Register your models here.

class MockOlympiadIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = exams.models.MockOlympiad
		fields = ('id', 'family', 'number', 'jmo_url', 'usamo_url', 'solns_url',)

@admin.register(exams.models.MockOlympiad)
class MockOlympiadAdmin(ImportExportModelAdmin):
	list_display = ('family', 'number',)
	search_fields = ('family', 'number',)
	resource_class = MockOlympiadIEResource

class AssignmentIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = exams.models.Assignment
		fields = ('id', 'semester', 'name', 'olympiad', 'due_date',)

@admin.register(exams.models.Assignment)
class AssignmentAdmin(ImportExportModelAdmin):
	list_display = ('id', 'semester', 'name', 'olympiad', 'due_date',)
	search_fields = ('olympiad__family', 'name',)
	resource_class = AssignmentIEResource
