from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import (
    JoinRecord,
    OIMEAttempt,
    OIMEComment,
    OIMEContributor,
    OIMEParticipation,
    OIMEProposal,
    OIMEYear,
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


@admin.register(OIMEYear)
class OIMEYearAdmin(admin.ModelAdmin[OIMEYear]):
    list_display = ["name", "active"]
    list_filter = ["active"]


@admin.register(OIMEContributor)
class OIMEContributorAdmin(admin.ModelAdmin[OIMEContributor]):
    list_display = ["display_name", "user"]
    search_fields = ["display_name", "user__username"]


@admin.register(OIMEParticipation)
class OIMEParticipationAdmin(admin.ModelAdmin[OIMEParticipation]):
    list_display = ["contributor", "year", "is_serious"]
    list_filter = ["year", "is_serious"]
    search_fields = ["contributor__display_name"]


@admin.register(OIMEProposal)
class OIMEProposalAdmin(admin.ModelAdmin[OIMEProposal]):
    list_display = ["__str__", "author", "subject", "difficulty", "archived", "created_at"]
    list_filter = ["subject", "difficulty", "archived"]
    search_fields = ["author__display_name", "statement"]
    readonly_fields = ["created_at", "updated_at"]
    filter_horizontal = ["upvotes"]


@admin.register(OIMEAttempt)
class OIMEAttemptAdmin(admin.ModelAdmin[OIMEAttempt]):
    list_display = ["contributor", "proposal", "year", "status", "wrong_answers", "solve_time_seconds", "started_at"]
    list_filter = ["status", "year"]
    search_fields = ["contributor__display_name"]
    readonly_fields = ["started_at"]


@admin.register(OIMEComment)
class OIMECommentAdmin(admin.ModelAdmin[OIMEComment]):
    list_display = ["author", "proposal", "created_at"]
    search_fields = ["author__display_name", "content"]
    readonly_fields = ["created_at"]
