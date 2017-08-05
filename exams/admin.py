from django.contrib import admin

import exams

# Register your models here.

@admin.register(exams.models.MockOlympiad)
class MockOlympiadAdmin(admin.ModelAdmin):
	list_display = ('family', 'number',)
	search_fields = ('family', 'number',)

@admin.register(exams.models.Assignment)
class AssignmentAdmin(admin.ModelAdmin):
	list_display = ('id', 'semester', 'name', 'olympiad', 'due_date',)
	search_fields = ('olympiad__family', 'name',)
