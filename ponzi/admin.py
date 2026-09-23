from django.contrib import admin

from .models import PonziInvestment, PonziScheme


@admin.register(PonziScheme)
class PonziSchemeAdmin(admin.ModelAdmin):
    list_display = ("title", "start_date", "collapsed_at", "collapsed_by")
    search_fields = ("title",)
    autocomplete_fields = ("collapsed_by",)


@admin.register(PonziInvestment)
class PonziInvestmentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "scheme",
        "amount",
        "target_tier",
        "created_at",
        "upgraded_at",
        "withdrawn_at",
        "payout",
    )
    list_filter = ("scheme", "target_tier")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__username",
    )
    autocomplete_fields = ("user",)
