from django.contrib import admin

from opal.models import OpalAttempt, OpalHunt, OpalPuzzle


@admin.register(OpalHunt)
class OpalHuntAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "active",
        "start_date",
    )
    list_filter = ("active",)
    search_fields = (
        "name",
        "slug",
    )
    list_display_links = (
        "name",
        "slug",
    )


@admin.register(OpalPuzzle)
class OpalPuzzleAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "hunt",
        "num_to_unlock",
        "slug",
        "title",
        "answer",
        "content",
        "achievement",
    )
    list_display_links = ("pk", "slug", "title")
    list_filter = (
        "hunt",
        ("content", admin.EmptyFieldListFilter),
        ("achievement", admin.EmptyFieldListFilter),
    )
    search_fields = ("hunt__name", "slug", "title")


@admin.register(OpalAttempt)
class OpalAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "created_at",
        "puzzle",
        "user",
        "guess",
        "is_correct",
        "excused",
    )
    list_display_links = (
        "pk",
        "puzzle",
        "user",
        "guess",
        "created_at",
    )
    list_filter = (
        "is_correct",
        "excused",
        "puzzle__hunt",
    )
    search_fields = ("pk",)
    readonly_fields = ("created_at",)
