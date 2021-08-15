from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import Problem, Hint


class HintInline(admin.TabularInline):
	model = Hint
	fields = ('number', 'keywords', 'content')
	extra = 0


@admin.register(Problem)
class ProblemAdmin(VersionAdmin):
	list_display = (
		'id',
		'puid',
		'source',
		'description',
	)
	search_fields = (
		'puid',
		'source',
		'description',
	)
	list_per_page = 100
	inlines = (HintInline,)


@admin.register(Hint)
class HintAdmin(VersionAdmin):
	list_display = (
		'id',
		'problem',
		'number',
		'keywords',
		'content',
	)
	search_fields = (
		'number',
		'problem__source',
		'keywords',
		'content',
	)
	autocomplete_fields = ('problem',)
	list_per_page = 30
