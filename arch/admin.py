from django.contrib import admin
from reversion.admin import VersionAdmin

from . import models


class HintInline(admin.TabularInline):
	model = models.Hint
	fields = ('number', 'keywords', 'content')
	extra = 0

@admin.register(models.Problem)
class ProblemAdmin(VersionAdmin):
	list_display = ('id', 'puid', 'source', 'description',)
	search_fields = ('puid', 'source', 'description',)
	list_per_page = 100
	inlines = (HintInline,)

@admin.register(models.Hint)
class HintAdmin(VersionAdmin):
	list_display = ('id', 'problem', 'number', 'keywords', 'content',)
	search_fields = ('number', 'problem__source', 'keywords', 'content',)
	autocomplete_fields = ('problem',)
	list_per_page = 30
