# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import dashboard

from django.contrib import admin

@admin.register(dashboard.models.UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
	list_display = ('id', 'file_content', 'description', 'created_at',
			'benefactor', 'unit', 'file_type', 'owner',)
	search_fields = ('description',)
