from django.contrib import admin
from reversion.admin import VersionAdmin
from . import models

@admin.register(models.Problem)
class ProblemAdmin(VersionAdmin):
	list_display = ('id', 'source', 'description', 'group',)
	search_fields = ('source', 'description',)
	list_filter = ('group',)
	list_per_page = 100
	autocomplete_fields = ('group',)

@admin.register(models.Hint)
class HintAdmin(VersionAdmin):
	list_display = ('number', 'problem', 'keywords', 'content',)
	search_fields = ('number', 'problem', 'keywords', 'content',)
	list_filter = ('problem__group',)
	autocomplete_fields = ('problem',)
	list_per_page = 30
