from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import Hint, Problem


class HintInline(admin.TabularInline):
	model = Hint
	fields = ('number', 'keywords', 'content')
	extra = 0


@admin.register(Problem)
class ProblemAdmin(VersionAdmin):
	list_display = (
		'id',
		'puid',
	)
	search_fields = ('puid', )
	list_per_page = 100
	inlines = (HintInline, )


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
		'keywords',
		'content',
	)
	autocomplete_fields = ('problem', )
	list_per_page = 30
