from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import (
    JoinRecord,
    OIMEComment,
    OIMEContributor,
    OIMEFight,
    OIMEProposal,
    OIMESelection,
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
    autocomplete_fields = ("user",)
    list_select_related = ("tube", "user")


@admin.register(OIMEContributor)
class OIMEContributorAdmin(admin.ModelAdmin[OIMEContributor]):
    ordering = ("display_name",)
    list_display = ("display_name", "user", "casual_mode")
    list_filter = ("casual_mode",)
    search_fields = ("display_name", "user__username")
    autocomplete_fields = ("user",)


@admin.register(OIMEProposal)
class OIMEProposalAdmin(admin.ModelAdmin[OIMEProposal]):
    list_display = (
        "label",
        "title",
        "credit_display",
        "difficulty_display",
        "created_at",
        "archived",
        "is_draft",
    )
    list_display_links = ("label", "title")
    list_filter = ("subject", "difficulty", "archived", "is_draft")
    search_fields = ("author__display_name", "title", "statement")
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("upvotes",)
    list_select_related = ("author",)
    actions = ("archive_problems", "unarchive_problems")
    autocomplete_fields = ("author",)

    @admin.action(description="Archive selected problems")
    def archive_problems(
        self, request: HttpRequest, queryset: QuerySet[OIMEProposal]
    ) -> None:
        count = queryset.update(archived=True)
        self.message_user(request, f"Archived {count} problem(s).")

    @admin.action(description="Unarchive selected problems")
    def unarchive_problems(
        self, request: HttpRequest, queryset: QuerySet[OIMEProposal]
    ) -> None:
        count = queryset.update(archived=False)
        self.message_user(request, f"Unarchived {count} problem(s).")


@admin.register(OIMEFight)
class OIMEFightAdmin(admin.ModelAdmin[OIMEFight]):
    list_display = (
        "contributor",
        "proposal",
        "status",
        "wrong_answers",
        "time_display",
        "started_at",
    )
    list_filter = ("status",)
    search_fields = ("contributor__display_name",)
    readonly_fields = ("started_at",)
    autocomplete_fields = ("contributor",)

    def view_on_site(self, obj: OIMEFight) -> str:
        return obj.proposal.get_absolute_url()


@admin.register(OIMEComment)
class OIMECommentAdmin(admin.ModelAdmin[OIMEComment]):
    list_display = ("author", "proposal", "created_at")
    search_fields = ("author__display_name", "content")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("author",)

    def view_on_site(self, obj: OIMEComment) -> str:
        return obj.proposal.get_absolute_url()


class OIMESelectionInline(admin.TabularInline[OIMESelection, OIMEYear]):
    """Only the chosen problems: every deferred problem has a row too, and a year
    defers far more than it chooses. Deferred rows live in the selection admin."""

    model = OIMESelection
    extra = 0
    fields = ("proposal", "status", "editor", "notes")
    autocomplete_fields = ("proposal", "editor")

    def get_queryset(self, request: HttpRequest) -> QuerySet[OIMESelection]:
        return super().get_queryset(request).filter(OIMESelection.CHOSEN)


@admin.register(OIMEYear)
class OIMEYearAdmin(admin.ModelAdmin[OIMEYear]):
    list_display = (
        "display_name",
        "proposals_open_at",
        "proposals_close_at",
        "release_at",
    )
    list_display_links = ("display_name",)
    inlines = (OIMESelectionInline,)


@admin.register(OIMESelection)
class OIMESelectionAdmin(admin.ModelAdmin[OIMESelection]):
    list_display = ("proposal", "year", "status", "editor", "updated_at")
    list_display_links = ("proposal",)
    list_filter = ("year", "status")
    search_fields = ("proposal__title", "editor__display_name")
    autocomplete_fields = ("proposal", "editor")
    list_select_related = ("proposal", "year", "editor")
