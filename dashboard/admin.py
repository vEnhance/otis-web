# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import dashboard.models

from django.contrib import admin

@admin.register(dashboard.models.UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
	list_display = ('id', 'content', 'created_at', 'description',
			'benefactor', 'unit', 'category', 'owner',)
	search_fields = ('description',)
	list_filter = ('category',)
	list_per_page = 30
	autocomplete_fields = ('benefactor', 'unit', 'owner',)

@admin.register(dashboard.models.SemesterDownloadFile)
class SemesterDownloadFileAdmin(admin.ModelAdmin):
	list_display = ('id', 'semester', 'content', 'created_at', 'description',)
	search_fields = ('description',)
	list_filter = ('semester',)
	list_per_page = 30

@admin.register(dashboard.models.PSetSubmission)
class PSetSubmissionAdmin(admin.ModelAdmin):
	list_display = ('approved', 'student', 'unit', 'hours', 'clubs',)
	search_fields = ('unit__group__name',
			'student__user__first_name', 'student__user__last_name',
			'feedback', 'special_notes',)
	list_filter = ('approved', 'student__semester',)
	list_display_links = ('student', 'unit',)
	list_per_page = 30

@admin.register(dashboard.models.ProblemSuggestion)
class ProblemSuggestionAdmin(admin.ModelAdmin):
	list_display = ('id', 'student', 'source', 'description', 'resolved', 'notified',)
	search_fields = ('student__user__first_name', 'student__user__last_name', 'unit__group__name', 'source', 'description', 'statement', 'solution',  'comments',)
	list_filter = ('resolved', 'unit__group', 'student__semester',)
	autocomplete_fields = ('student', 'unit',)
	list_per_page = 50
