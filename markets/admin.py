from django.contrib import admin

from .models import Guess, Market

# Register your models here.


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
	list_display = (
		'slug',
		'title',
		'prompt',
		'start_date',
		'end_date',
		'semester',
	)
	list_filter = (
		'semester__active',
		'semester',
	)
	search_fields = (
		'slug',
		'title',
		'prompt',
	)


@admin.register(Guess)
class GuessAdmin(admin.ModelAdmin):
	list_display = (
		'market',
		'value',
		'created_at',
		'user',
		'public',
	)
	list_filter = (
		'market__semester__active',
		'market__semester',
		'public',
	)
	search_fields = (
		'user__first_name',
		'user__last_name',
		'market',
	)
	autocomplete_fields = ('market', )
