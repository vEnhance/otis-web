from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

import exams.models

# Register your models here.

class PracticeExamIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = exams.models.PracticeExam
		fields = ('family', 'is_test', 'number', 'pdf_url', 'id',
				'start_date', 'due_date',
				'answer1', 'answer2', 'answer3', 'answer4', 'answer5',
				'url1', 'url2', 'url3', 'url4', 'url5',
				)

@admin.register(exams.models.PracticeExam)
class PracticeExamAdmin(ImportExportModelAdmin):
	list_display = ('family', 'number',  'is_test', 'start_date', 'due_date', 'id', )
	list_filter = ('family', 'is_test',)
	list_display_links = ('family', 'number',)
	search_fields = ('family', 'number',)
	resource_class = PracticeExamIEResource

@admin.register(exams.models.ExamAttempt)
class ExamAttemptAdmin(ImportExportModelAdmin):
	list_display = ('quiz', 'student', 'score', 'submit_time',)
	list_filter = ('quiz', 'quiz__family',)
	list_display_links = ('quiz',)
