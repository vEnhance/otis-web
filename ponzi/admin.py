from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import PonziInvestment, PonziScheme, PonziTimer


@admin.register(PonziScheme)
class PonziSchemeAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "start_date",
        "gestation_period",
        "collapsed_at",
        "collapsed_by",
    )
    search_fields = ("title",)
    autocomplete_fields = ("collapsed_by",)


class PonziTimerInline(admin.TabularInline):
    model = PonziTimer
    fields = ("tier", "started_at", "inferred")
    extra = 0


@admin.register(PonziInvestment)
class PonziInvestmentAdmin(admin.ModelAdmin):
    inlines = (PonziTimerInline,)
    list_display = (
        "user",
        "scheme",
        "amount",
        "target_tier",
        "created_at",
        "withdrawn_at",
        "payout",
    )
    list_filter = ("scheme",)
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__username",
    )
    autocomplete_fields = ("user",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[PonziInvestment]:
        return super().get_queryset(request).prefetch_related("timers")

    def view_on_site(self, obj: PonziInvestment) -> str:
        return obj.scheme.get_absolute_url()


@admin.register(PonziTimer)
class PonziTimerAdmin(admin.ModelAdmin):
    list_display = ("investment", "tier", "started_at", "inferred")
    list_filter = ("investment__scheme", "tier", "inferred")
    list_select_related = ("investment__user", "investment__scheme")
    search_fields = (
        "investment__user__first_name",
        "investment__user__last_name",
        "investment__user__username",
    )
    autocomplete_fields = ("investment",)

    def view_on_site(self, obj: PonziTimer) -> str:
        return obj.investment.scheme.get_absolute_url()
