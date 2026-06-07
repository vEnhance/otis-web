from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import JoinRecord, OIMEAttempt, OIMEComment, OIMEProposal, OIMESolverRole, Tube


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


@admin.register(OIMEProposal)
class OIMEProposalAdmin(admin.ModelAdmin[OIMEProposal]):
    list_display = ["__str__", "author", "subject", "difficulty", "created_at"]
    list_filter = ["subject", "difficulty"]
    search_fields = ["author__username", "statement"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(OIMESolverRole)
class OIMESolverRoleAdmin(admin.ModelAdmin[OIMESolverRole]):
    list_display = ["user", "is_serious"]
    list_filter = ["is_serious"]
    search_fields = ["user__username"]


@admin.register(OIMEAttempt)
class OIMEAttemptAdmin(admin.ModelAdmin[OIMEAttempt]):
    list_display = ["user", "proposal", "status", "wrong_answers", "solve_time_seconds", "started_at"]
    list_filter = ["status"]
    search_fields = ["user__username"]
    readonly_fields = ["started_at"]


@admin.register(OIMEComment)
class OIMECommentAdmin(admin.ModelAdmin[OIMEComment]):
    list_display = ["author", "proposal", "created_at"]
    search_fields = ["author__username", "content"]
    readonly_fields = ["created_at"]
