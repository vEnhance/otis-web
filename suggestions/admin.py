from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import ProblemSuggestion


@admin.register(ProblemSuggestion)
class ProblemSuggestionAdmin(admin.ModelAdmin):
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    list_display = (
        "pk",
        "user",
        "source",
        "status",
        "description",
        "acknowledge",
        "eligible",
    )
    search_fields = (
        "user__first_name",
        "user__last_name",
        "unit__group__name",
        "source",
        "description",
        "statement",
        "solution",
        "comments",
    )
    list_filter = (
        "eligible",
        "status",
        "unit__group",
    )
    autocomplete_fields = (
        "user",
        "unit",
    )
    list_display_links = (
        "pk",
        "user",
        "source",
        "description",
    )
    list_per_page = 50

    def mark_eligible(
        self, request: HttpRequest, queryset: QuerySet[ProblemSuggestion]
    ):
        queryset.update(eligible=True)

    def mark_uneligible(
        self, request: HttpRequest, queryset: QuerySet[ProblemSuggestion]
    ):
        queryset.update(eligible=False)

    actions = [
        "mark_eligible",
        "mark_uneligible",
    ]
