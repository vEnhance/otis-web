from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from reversion.admin import VersionAdmin

from .models import Hint, Problem, Vote


class HintInline(admin.TabularInline):
    model = Hint
    fields = ("number", "keywords", "content")
    extra = 0


class ProblemIEResource(resources.ModelResource):
    class Meta:
        skip_unchanged = True
        model = Problem
        fields = (
            "id",
            "puid",
            "hyperlink",
        )
        export_order = fields


@admin.register(Problem)
class ProblemAdmin(ImportExportModelAdmin):
    list_display = ("pk", "puid", "hyperlink", "niceness")
    list_display_links = (
        "pk",
        "puid",
    )

    search_fields = ("puid",)
    list_per_page = 100
    inlines = (HintInline,)
    resource_class = ProblemIEResource


@admin.register(Hint)
class HintAdmin(VersionAdmin):
    list_display = (
        "pk",
        "problem",
        "number",
        "keywords",
        "content",
    )
    search_fields = (
        "number",
        "keywords",
        "content",
    )
    autocomplete_fields = ("problem",)
    list_per_page = 30


@admin.register(Vote)
class VoteAdmin(VersionAdmin):
    readonly_fields = ("created_at", "updated_at")
    list_display = (
        "problem",
        "user",
        "niceness",
    )
    search_fields = ("problem__puid", "user__username")
    autocomplete_fields = ("problem",)
    list_per_page = 30
