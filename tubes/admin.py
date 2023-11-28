from django.contrib import admin
from django.db.models.query import QuerySet
from django.http.request import HttpRequest

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
    list_filter = ("status",)


@admin.register(JoinRecord)
class JoinRecordAdmin(admin.ModelAdmin):
    list_display = ("pk", "tube", "user", "created_at", "success")
    list_display_links = ("pk", "tube", "user")
    list_filter = ("success",)

    def mark_failed(self, request: HttpRequest, queryset: QuerySet[JoinRecord]):
        queryset.update(success=False)
