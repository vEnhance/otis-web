from django.contrib import admin

from .models import Guess, Market

# Register your models here.


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = (
        'slug',
        'title',
        'prompt_truncated',
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

    @admin.display(description='Prompt')
    def prompt_truncated(self, obj: Market) -> str:
        NUM_CHAR = 200
        text = obj.prompt
        return text[:NUM_CHAR] + ("..." if len(text) > NUM_CHAR else "")


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
        'user__username',
        'market',
    )
    autocomplete_fields = ('market',)
