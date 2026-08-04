import os

from django.contrib import admin, messages
from django.forms import ModelForm
from django.http import HttpRequest

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
        "title",
        "slug",
        "is_uploaded",
        "credits",
        "answer",
        "hunt",
        "order",
        "num_to_unlock",
    )
    list_display_links = ("pk", "title", "slug")
    list_filter = (
        "hunt",
        ("content", admin.EmptyFieldListFilter),
        ("achievement", admin.EmptyFieldListFilter),
    )
    search_fields = ("hunt__name", "slug", "title")

    def save_model(
        self,
        request: HttpRequest,
        obj: OpalPuzzle,
        form: ModelForm[OpalPuzzle],
        change: bool,
    ) -> None:
        if "content" in form.changed_data and obj.content:
            uploaded_name = os.path.basename(obj.content.name or "")
            if uploaded_name != obj.slug + ".pdf":
                messages.warning(
                    request,
                    f"The file {uploaded_name} does not match the slug {obj.slug}; "
                    "it was saved under that name anyway, but check you uploaded "
                    "the right file.",
                )
        super().save_model(request, obj, form, change)


@admin.register(OpalAttempt)
class OpalAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "created_at",
        "puzzle",
        "user",
        "guess",
        "is_correct",
        "is_close",
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
