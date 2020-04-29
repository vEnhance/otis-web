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
	list_display = ('family', 'number',  'is_test', 'start_date', 'due_date', 'id', )
	list_filter = ('family', 'is_test',)
	list_display_links = ('family', 'number',)
	search_fields = ('family', 'number',)
	resource_class = PracticeExamIEResource
