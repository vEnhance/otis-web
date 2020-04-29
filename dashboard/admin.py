# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import dashboard

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
