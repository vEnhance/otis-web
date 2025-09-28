from datetime import timedelta

from django.contrib import admin
from django.db.models import F
from django.db.models.query import QuerySet
from django.http.request import HttpRequest

from .models import Guess, Market


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = (
        "slug",
        "title",
        "prompt_truncated",
        "int_guesses_only",
        "start_date",
        "end_date",
        "semester",
    )
    list_filter = (
        "semester__active",
        "semester",
    )
    search_fields = (
        "slug",
        "title",
        "prompt",
    )

    @admin.display(description="Prompt")
    def prompt_truncated(self, obj: Market) -> str:
        NUM_CHAR = 200
        text = obj.prompt
        return text[:NUM_CHAR] + ("..." if len(text) > NUM_CHAR else "")

    actions = [
        "postpone_market",
        "hasten_market",
    ]

    def shift_market(self, queryset: QuerySet[Market], num_days: int):
        queryset.update(
            start_date=F("start_date") + timedelta(days=num_days),
            end_date=F("end_date") + timedelta(days=num_days),
        )

    @admin.action(description="Postpone market by one week")
    def postpone_market(self, request: HttpRequest, queryset: QuerySet[Market]):
        self.shift_market(queryset, num_days=7)

    @admin.action(description="Move market one week earlier")
    def hasten_market(self, request: HttpRequest, queryset: QuerySet[Market]):
        self.shift_market(queryset, num_days=-7)


@admin.register(Guess)
class GuessAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at",)
    list_display = (
        "market",
        "value",
        "created_at",
        "user",
        "public",
        "is_latest",
        "score",
    )
    list_filter = (
        "market__semester__active",
        "market__semester",
        "public",
        "is_latest",
    )
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__username",
        "market",
    )
    autocomplete_fields = ("market",)
    ordering = ("-created_at",)
    
    def get_queryset(self, request: HttpRequest) -> QuerySet[Guess]:
        return super().get_queryset(request).select_related("market", "user")
