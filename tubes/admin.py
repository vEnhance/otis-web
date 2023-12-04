from django.contrib import admin

from .models import JoinRecord, Tube


@admin.register(Tube)
class TubeAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "display_name",
        "status",
        "main_url",
        "accepting_signups",
    )
    list_display_links = (
        "pk",
        "display_name",
    )
    list_filter = ("status", "accepting_signups")


@admin.register(JoinRecord)
class JoinRecordAdmin(admin.ModelAdmin):
    list_display = ("pk", "tube", "user", "activation_time")
    list_display_links = ("pk", "tube", "user")
    list_filter = (("user", admin.EmptyFieldListFilter),)
