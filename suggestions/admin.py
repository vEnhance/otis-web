from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import ProblemSuggestion


@admin.register(ProblemSuggestion)
class ProblemSuggestionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'source',
        'description',
        'acknowledge',
        'eligible',
        'resolved',
    )
    search_fields = (
        'user__first_name',
        'user__last_name',
        'unit__group__name',
        'source',
        'description',
        'statement',
        'solution',
        'comments',
    )
    list_filter = (
        'eligible',
        'resolved',
        'unit__group',
    )
    autocomplete_fields = (
        'user',
        'unit',
    )
    list_display_links = (
        'id',
        'user',
        'source',
        'description',
    )
    list_per_page = 50

    def mark_eligible(self, request: HttpRequest, queryset: QuerySet[ProblemSuggestion]):
        queryset.update(eligible=True)

    def mark_uneligible(self, request: HttpRequest, queryset: QuerySet[ProblemSuggestion]):
        queryset.update(eligible=False)

    actions = [
        'mark_eligible',
        'mark_uneligible',
    ]
