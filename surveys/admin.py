from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest
from django.utils.text import Truncator

from surveys.models import GMFeedback, InstructorComment, Survey, SurveyCompletion

EXCERPT_LENGTH = 80


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "name",
        "semester",
        "opens_at",
        "closes_at",
        "achievement",
        "achievement_awarded_at",
        "num_completions",
    )
    list_display_links = ("pk", "name")
    list_filter = ("semester",)
    search_fields = ("name",)
    autocomplete_fields = ("achievement",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Survey]:
        return (
            super()
            .get_queryset(request)
            .select_related("semester", "achievement")
            .annotate(completion_count=Count("surveycompletion"))
        )

    @admin.display(description="Completions", ordering="completion_count")
    def num_completions(self, obj: Survey) -> int:
        return obj.completion_count  # type: ignore[attr-defined]


@admin.register(SurveyCompletion)
class SurveyCompletionAdmin(admin.ModelAdmin):
    list_display = ("student", "survey")
    list_filter = ("survey__semester", "survey")
    search_fields = (
        "student__user__first_name",
        "student__user__last_name",
        "student__user__username",
    )
    list_select_related = ("student__user", "student__semester", "survey__semester")
    autocomplete_fields = ("student",)


@admin.register(GMFeedback)
class GMFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "survey",
        "student",
        "satisfaction",
        "is_read",
        "has_reply",
        "essay_excerpt",
    )
    list_display_links = ("pk", "survey")
    list_filter = (
        "survey__semester",
        "survey",
        "is_read",
        ("student", admin.EmptyFieldListFilter),
        ("reply", admin.EmptyFieldListFilter),
    )
    search_fields = (
        "essay",
        "anything_else",
        "reply",
        "student__user__first_name",
        "student__user__last_name",
    )
    list_select_related = ("survey__semester", "student__user", "student__semester")
    autocomplete_fields = ("student",)

    @admin.display(description="Replied", boolean=True)
    def has_reply(self, obj: GMFeedback) -> bool:
        return bool(obj.reply)

    @admin.display(description="Essay")
    def essay_excerpt(self, obj: GMFeedback) -> str:
        return Truncator(obj.essay).chars(EXCERPT_LENGTH)


@admin.register(InstructorComment)
class InstructorCommentAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "survey",
        "assistant",
        "student",
        "is_read",
        "comments_excerpt",
    )
    list_display_links = ("pk", "survey")
    list_filter = (
        "survey__semester",
        "survey",
        "assistant",
        "is_read",
        ("student", admin.EmptyFieldListFilter),
    )
    search_fields = (
        "comments",
        "student__user__first_name",
        "student__user__last_name",
    )
    list_select_related = (
        "survey__semester",
        "assistant__user",
        "student__user",
        "student__semester",
    )
    autocomplete_fields = ("student", "assistant")

    @admin.display(description="Comments")
    def comments_excerpt(self, obj: InstructorComment) -> str:
        return Truncator(obj.comments).chars(EXCERPT_LENGTH)
