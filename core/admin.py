from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from import_export import fields, resources, widgets
from import_export.admin import ImportExportModelAdmin

from core.models import UserProfile

from .models import Semester, Unit, UnitGroup

# Register your models here.


class SemesterResource(resources.ModelResource):
    class Meta:
        skip_unchanged = True
        model = Semester
        fields = (
            "id",
            "name",
            "active",
            "show_invoices",
            "exam_family",
        )
        export_order = fields


@admin.register(Semester)
class SemesterAdmin(ImportExportModelAdmin):
    list_display = (
        "name",
        "pk",
        "active",
        "show_invoices",
        "exam_family",
    )
    search_fields = ("name",)
    resource_class = SemesterResource


class UnitIEResource(resources.ModelResource):
    group_name = fields.Field(
        column_name="group_name",
        attribute="group",
        widget=widgets.ForeignKeyWidget(UnitGroup, "name"),  # type: ignore
    )

    class Meta:
        skip_unchanged = True
        model = Unit
        fields = (
            "id",
            "group_name",
            "code",
            "position",
        )
        export_order = fields


@admin.register(Unit)
class UnitAdmin(ImportExportModelAdmin):
    list_display = (
        "group",
        "code",
        "pk",
        "list_display_position",
    )
    list_filter = ("group__subject",)
    search_fields = ("group__name", "code")
    autocomplete_fields = ("group",)
    ordering = ("position",)
    resource_class = UnitIEResource
    list_per_page = 150
    list_max_show_all = 400


class UnitInline(admin.TabularInline):
    model = Unit
    fields = (
        "code",
        "position",
    )
    extra = 0


class UnitGroupIEResource(resources.ModelResource):
    class Meta:
        skip_unchanged = True
        model = UnitGroup
        fields = (
            "id",
            "subject",
            "name",
            "slug",
            "description",
            "artwork",
            "artwork_thumb_md",
            "artwork_thumb_sm",
            "artist_name",
        )
        export_order = fields


@admin.register(UnitGroup)
class UnitGroupAdmin(ImportExportModelAdmin):
    list_display = (
        "pk",
        "name",
        "subject",
        "description",
        "hidden",
        "artist_name",
    )
    list_display_links = (
        "pk",
        "name",
    )
    search_fields = (
        "name",
        "description",
    )
    list_filter = ("subject", "hidden")
    resource_class = UnitGroupIEResource
    list_per_page = 150
    list_max_show_all = 400
    inlines = (UnitInline,)
    actions = ["set_default_artwork"]

    @admin.action(description="Set default artwork paths based on slug")
    def set_default_artwork(
        self, request: HttpRequest, queryset: QuerySet[UnitGroup]
    ) -> None:
        """Set artwork fields to default values based on the unit group's slug."""
        unit_groups_to_update = []
        for unit_group in queryset:
            unit_group.artwork = f"artwork/{unit_group.slug}.png"
            unit_group.artwork_thumb_md = f"artwork-thumb-md/{unit_group.slug}.png"
            unit_group.artwork_thumb_sm = f"artwork-thumb-sm/{unit_group.slug}.png"
            unit_groups_to_update.append(unit_group)

        updated_count = len(unit_groups_to_update)
        UnitGroup.objects.bulk_update(
            unit_groups_to_update,
            ["artwork", "artwork_thumb_md", "artwork_thumb_sm"],
        )

        self.message_user(
            request,
            f"Successfully set default artwork paths for {updated_count} unit group(s).",
        )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "user",
        "last_seen",
        "show_bars",
        "show_completed_by_default",
        "show_locked_by_default",
        "dynamic_progress",
    )
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__username",
    )
