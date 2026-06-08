from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import (
    JoinRecord,
    OIMEComment,
    OIMEContributor,
    OIMEFight,
    OIMEProposal,
    Tube,
)


@admin.register(Tube)
class TubeAdmin(admin.ModelAdmin[Tube]):
    list_display = ("pk", "display_name", "status", "main_url", "accepting_signups")
    list_display_links = ("pk", "display_name")
    list_filter = ("status", "accepting_signups")


class JoinRecordResource(resources.ModelResource):
    class Meta:
        skip_unchanged = True
        model = JoinRecord
        fields = ("id", "tube", "activation_time", "invite_url")
        export_order = fields


@admin.register(JoinRecord)
class JoinRecordAdmin(ImportExportModelAdmin):
    list_display = ("pk", "tube", "user", "activation_time")
    list_display_links = ("pk", "tube", "user")
    list_filter = (("user", admin.EmptyFieldListFilter),)
    search_fields = ("user__username", "invite_url")
    resource_class = JoinRecordResource


@admin.register(OIMEContributor)
class OIMEContributorAdmin(admin.ModelAdmin[OIMEContributor]):
    list_display = ["display_name", "user", "spoil_before"]
    search_fields = ["display_name", "user__username"]


@admin.register(OIMEProposal)
class OIMEProposalAdmin(admin.ModelAdmin[OIMEProposal]):
    list_display = [
        "__str__",
        "title",
        "author",
        "subject",
        "difficulty",
        "archived",
        "created_at",
    ]
    list_filter = ["subject", "difficulty", "archived"]
    search_fields = ["author__display_name", "title", "statement"]
    readonly_fields = ["created_at", "updated_at"]
    filter_horizontal = ["upvotes"]


@admin.register(OIMEFight)
class OIMEFightAdmin(admin.ModelAdmin[OIMEFight]):
    list_display = [
        "contributor",
        "proposal",
        "status",
        "wrong_answers",
        "solve_time_seconds",
        "started_at",
    ]
    list_filter = ["status"]
    search_fields = ["contributor__display_name"]
    readonly_fields = ["started_at"]


@admin.register(OIMEComment)
class OIMECommentAdmin(admin.ModelAdmin[OIMEComment]):
    list_display = ["author", "proposal", "created_at"]
    search_fields = ["author__display_name", "content"]
    readonly_fields = ["created_at"]
