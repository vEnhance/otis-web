# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from import_export import resources, widgets, fields
from import_export.admin import ImportExportModelAdmin

import dashboard.models

from django.contrib import admin
from django.http import HttpRequest
from django.db.models import QuerySet

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

@admin.register(dashboard.models.PSet)
class PSetAdmin(admin.ModelAdmin):
	list_display = ('approved', 'student', 'unit', 'hours', 'clubs',)
	search_fields = ('unit__group__name',
			'student__user__first_name', 'student__user__last_name',
			'feedback', 'special_notes',)
	list_filter = ('approved', 'student__semester',)
	list_display_links = ('student', 'unit',)
	list_per_page = 30
	def approve_pset(self, request: HttpRequest, queryset: QuerySet):
		queryset.update(approved=True)
	def reject_pset(self, request: HttpRequest, queryset: QuerySet):
		queryset.update(approved=False)
	actions = ['approve_pset', 'reject_pset',]

@admin.register(dashboard.models.ProblemSuggestion)
class ProblemSuggestionAdmin(admin.ModelAdmin):
	list_display = ('id', 'student', 'source', 'description', 'resolved', 'notified',)
	search_fields = ('student__user__first_name', 'student__user__last_name', 'unit__group__name', 'source', 'description', 'statement', 'solution',  'comments',)
	list_filter = ('resolved', 'unit__group', 'student__semester',)
	autocomplete_fields = ('student', 'unit',)
	list_per_page = 50

class LevelIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = dashboard.models.Level
		fields = ('id', 'threshold', 'name')

@admin.register(dashboard.models.Level)
class LevelAdmin(ImportExportModelAdmin):
	list_display = ('threshold', 'name',)
	search_fields = ('name',)
	resource_class = LevelIEResource
