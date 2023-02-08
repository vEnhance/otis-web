from django.contrib import admin

from .models import HanabiContest, HanabiParticipation, HanabiPlayer, HanabiReplay


@admin.register(HanabiContest)
class HanabiContestAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "variant_name",
        "num_players",
        "num_suits",
        "end_date",
        "processed",
    )
    list_display_links = (
        "pk",
        "variant_name",
    )
    list_filter = (
        "num_players",
        "num_suits",
    )
    search_fields = (
        "pk",
        "variant_name",
    )


@admin.register(HanabiPlayer)
class HanabiPlayerAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at",)
    list_display = (
        "pk",
        "user",
        "name",
        "hanab_username",
    )
    list_display_links = (
        "pk",
        "user",
    )
    search_fields = (
        "pk",
        "user__username",
        "hanab_username",
    )


@admin.register(HanabiReplay)
class HanabiReplayAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "contest",
        "replay_id",
        "game_score",
        "turn_count",
        "spades_score",
    )
    list_display_links = (
        "pk",
        "contest",
        "replay_id",
    )
    list_filter = (
        "game_score",
        "contest__processed",
    )
    search_fields = (
        "pk",
        "contest__variant_name",
    )


@admin.register(HanabiParticipation)
class HanabiParticipationAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "player",
        "replay",
    )
    list_display_links = (
        "pk",
        "player",
        "replay",
    )
    list_filter = ("replay__contest__processed",)
    search_fields = (
        "player__hanab_username",
        "player__user__username",
        "replay__contest__variant_name",
    )


# Register your models here.
