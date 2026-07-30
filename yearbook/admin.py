from django.contrib import admin

from .models import YearbookEntry


@admin.register(YearbookEntry)
class YearbookEntryAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "user",
        "tagline",
        "country",
        "graduation_year",
        "university",
        "created_at",
    )
    list_display_links = ("pk", "user")
    list_filter = (
        "country",
        ("avatar", admin.EmptyFieldListFilter),
    )
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "tagline",
        "university",
    )
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
