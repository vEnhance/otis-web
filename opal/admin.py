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
        "slug",
        "title",
        "answer",
        "num_to_unlock",
        "content",
    )
    list_display_links = ("pk", "slug", "title")
    list_filter = (
        "hunt",
        ("content", admin.EmptyFieldListFilter),
    )
    search_fields = ("hunt__name", "slug", "title")


@admin.register(OpalAttempt)
class OpalAttemptAdmin(admin.ModelAdmin):
    list_display = ("pk", "puzzle", "user", "guess", "is_correct", "created_at")
    list_display_links = (
        "pk",
        "puzzle",
    )
    list_filter = ("is_correct",)
    search_fields = ("pk",)
