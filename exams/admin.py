from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import ExamAttempt, MockCompleted, PracticeExam

# Register your models here.


class PracticeExamIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = PracticeExam
		fields = (
			'family',
			'is_test',
			'number',
			'id',
			'start_date',
			'due_date',
			'answer1',
			'answer2',
			'answer3',
			'answer4',
			'answer5',
			'url1',
			'url2',
			'url3',
			'url4',
			'url5',
		)


@admin.register(PracticeExam)
class PracticeExamAdmin(ImportExportModelAdmin):
	list_display = (
		'family',
		'get_number_display',
		'is_test',
		'start_date',
		'due_date',
		'id',
	)
	list_filter = (
		'family',
		'is_test',
	)
	list_display_links = (
		'family',
		'get_number_display',
	)
	search_fields = (
		'family',
		'number',
	)
	resource_class = PracticeExamIEResource


@admin.register(ExamAttempt)
class ExamAttemptAdmin(ImportExportModelAdmin):
	list_display = (
		'quiz',
		'student',
		'score',
		'submit_time',
		'guess1',
		'guess2',
		'guess3',
		'guess4',
		'guess5',
	)
	list_filter = (
		'student__semester__active',
		'quiz',
		'student__semester',
		'quiz__family',
	)
	list_display_links = ('quiz', )


@admin.register(MockCompleted)
class MockCompletedAdmin(admin.ModelAdmin):
	list_display = (
		'exam',
		'student',
	)
	list_filter = (
		'student__semester__active',
		'exam',
		'student__semester',
	)
