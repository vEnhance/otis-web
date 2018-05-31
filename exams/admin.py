from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

import exams

# Register your models here.

class PracticeExamIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = exams.models.PracticeExam
		fields = ('family', 'is_test', 'number', 'pdf_url', 'id', 'start_date', 'due_date',)

@admin.register(exams.models.PracticeExam)
class PracticeExamAdmin(ImportExportModelAdmin):
	list_display = ('id', 'family', 'is_test', 'number', 'start_date', 'due_date',)
	list_filter = ('family', 'is_test',)
	search_fields = ('family', 'number',)
	resource_class = PracticeExamIEResource
