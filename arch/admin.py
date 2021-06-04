from django.contrib import admin
from reversion.admin import VersionAdmin
from . import models

@admin.register(models.Problem)
class ProblemAdmin(VersionAdmin):
	list_display = ('id', 'puid', 'source', 'description',)
	search_fields = ('puid', 'source', 'description',)
	list_per_page = 100

@admin.register(models.Hint)
class HintAdmin(VersionAdmin):
	list_display = ('id', 'problem', 'number', 'keywords', 'content',)
	search_fields = ('number', 'problem__source', 'keywords', 'content',)
	autocomplete_fields = ('problem',)
	list_per_page = 30
