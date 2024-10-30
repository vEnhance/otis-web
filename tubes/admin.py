from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

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


class JoinRecordResource(resources.ModelResource):
    class Meta:
        skip_unchanged = True
        model = JoinRecord
        fields = (
            "id",
            "tube",
            "activation_time",
            "invite_url",
        )
        export_order = fields


@admin.register(JoinRecord)
class JoinRecordAdmin(ImportExportModelAdmin):
    list_display = ("pk", "tube", "user", "activation_time")
    list_display_links = ("pk", "tube", "user")
    list_filter = (("user", admin.EmptyFieldListFilter),)
    search_fields = ("user__username", "invite_url")
    resource_class = JoinRecordResource
