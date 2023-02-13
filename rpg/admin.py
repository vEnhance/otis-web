from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import (  # NOQA
    Achievement,
    AchievementUnlock,
    BonusLevel,
    BonusLevelUnlock,
    Level,
    PalaceCarving,
    QuestComplete,
)

# Register your models here.


class AchievementIEResource(resources.ModelResource):
    class Meta:
        skip_unchanged = True
        model = Achievement
        fields = (
            "code",
            "name",
            "diamonds",
            "description",
            "solution",
        )


@admin.register(Achievement)
class AchievementAdmin(ImportExportModelAdmin):
    list_display = (
        "code",
        "name",
        "diamonds",
        "always_show_image",
        "description",
        "solution",
        "creator",
    )
    list_display_links = (
        "code",
        "name",
        "diamonds",
    )
    search_fields = (
        "code",
        "name",
        "description",
        "solution",
    )
    list_filter = (
        "always_show_image",
        ("creator", admin.EmptyFieldListFilter),
    )
    resource_class = AchievementIEResource


@admin.register(AchievementUnlock)
class AchievementUnlockAdmin(admin.ModelAdmin):
    readonly_fields = ("timestamp",)
    list_display = (
        "user",
        "achievement",
        "timestamp",
    )
    autocomplete_fields = (
        "user",
        "achievement",
    )
    search_fields = (
        "user__username",
        "achievement__name",
        "achievement__code",
    )


@admin.register(QuestComplete)
class QuestCompleteAdmin(admin.ModelAdmin):
    readonly_fields = ("timestamp",)
    list_display = (
        "pk",
        "title",
        "student",
        "spades",
        "timestamp",
        "category",
    )
    autocomplete_fields = ("student",)
    list_filter = (
        "student__semester",
        "category",
    )
    list_display_links = (
        "pk",
        "title",
        "student",
    )


@admin.register(BonusLevel)
class BonusLevelAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "group",
        "level",
    )
    autocomplete_fields = ("group",)
    search_fields = ("group__name",)


@admin.register(BonusLevelUnlock)
class BonusLevelUnlockAdmin(admin.ModelAdmin):
    readonly_fields = ("timestamp",)
    list_display = (
        "pk",
        "timestamp",
        "student",
        "bonus",
    )
    autocomplete_fields = (
        "student",
        "bonus",
    )
    list_filter = ("student__semester__active",)


@admin.register(PalaceCarving)
class PalaceCarvingAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at",)
    list_display = (
        "pk",
        "display_name",
        "created_at",
        "message",
    )
    list_display_links = (
        "pk",
        "display_name",
        "created_at",
    )


class LevelIEResource(resources.ModelResource):
    class Meta:
        skip_unchanged = True
        model = Level
        fields = (
            "id",
            "threshold",
            "name",
        )


@admin.register(Level)
class LevelAdmin(ImportExportModelAdmin):
    list_display = (
        "threshold",
        "name",
    )
    search_fields = ("name",)
    resource_class = LevelIEResource
