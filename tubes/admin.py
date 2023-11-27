from django.contrib import admin

from .models import JoinRecord, Tube


@admin.register(Tube)
class TubeAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "display_name",
        "status",
        "main_url",
        "has_join_url",
    )
    list_display_links = (
        "pk",
        "display_name",
    )


@admin.register(JoinRecord)
class JoinRecordAdmin(admin.ModelAdmin):
    list_display = ("pk", "tube", "user", "created_at")
    list_display_links = ("pk", "tube", "user")
