from django.contrib import admin

from .models import PonziInvestment, PonziScheme


@admin.register(PonziScheme)
class PonziSchemeAdmin(admin.ModelAdmin):
    list_display = ("title", "semester", "start_date", "collapsed_at", "collapsed_by")
    list_filter = ("semester__active", "semester")
    search_fields = ("title",)
    autocomplete_fields = ("collapsed_by",)


@admin.register(PonziInvestment)
class PonziInvestmentAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "scheme",
        "amount",
        "target_tier",
        "created_at",
        "upgraded_at",
        "withdrawn_at",
        "payout",
    )
    list_filter = ("scheme__semester__active", "scheme", "target_tier")
    search_fields = (
        "student__user__first_name",
        "student__user__last_name",
        "student__user__username",
    )
    autocomplete_fields = ("student",)
