from django.contrib import admin

from opal.models import OpalHunt


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
