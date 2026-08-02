import datetime

from django.contrib import admin
from django.db.models.query import QuerySet
from django.http.request import HttpRequest
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import ExamAttempt, MockCompleted, PracticeExam

# Register your models here.


def shift_years(date: datetime.date, num_years: int) -> datetime.date:
    """Returns the same calendar day, num_years later.

    A Feb 29 date lands on Feb 28 whenever the target year isn't a leap year.
    """
    try:
        return date.replace(year=date.year + num_years)
    except ValueError:
        return date.replace(year=date.year + num_years, day=28)


class PracticeExamIEResource(resources.ModelResource):
    class Meta:
        skip_unchanged = True
        model = PracticeExam
        fields = (
            "id",
            "family",
            "is_test",
            "number",
            "start_date",
            "due_date",
            "answer1",
            "answer2",
            "answer3",
            "answer4",
            "answer5",
            "url1",
            "url2",
            "url3",
            "url4",
            "url5",
        )
        export_order = fields


@admin.register(PracticeExam)
class PracticeExamAdmin(ImportExportModelAdmin):
    list_display = (
        "family",
        "get_number_display",
        "is_test",
        "start_date",
        "due_date",
        "pk",
    )
    list_filter = (
        "family",
        "is_test",
    )
    list_display_links = (
        "family",
        "get_number_display",
    )
    search_fields = (
        "family",
        "number",
    )
    resource_class = PracticeExamIEResource
    actions = ("postpone_two_years",)

    @admin.action(description="Move start and due dates forward by two calendar years")
    def postpone_two_years(
        self, request: HttpRequest, queryset: QuerySet[PracticeExam]
    ) -> None:
        exams = list(queryset)
        for exam in exams:
            if exam.start_date is not None:
                exam.start_date = shift_years(exam.start_date, num_years=2)
            if exam.due_date is not None:
                exam.due_date = shift_years(exam.due_date, num_years=2)
        PracticeExam.objects.bulk_update(exams, ("start_date", "due_date"))
        self.message_user(request, f"Postponed {len(exams)} exam(s) by two years.")


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    readonly_fields = ("submit_time",)
    list_display = (
        "quiz",
        "student",
        "score",
        "submit_time",
        "guess1",
        "guess2",
        "guess3",
        "guess4",
        "guess5",
    )
    list_filter = (
        "student__semester__active",
        "quiz",
        "student__semester",
        "quiz__family",
    )
    list_display_links = (
        "quiz",
        "student",
    )


@admin.register(MockCompleted)
class MockCompletedAdmin(admin.ModelAdmin):
    list_display = (
        "exam",
        "student",
        "created_at",
    )
    list_filter = (
        "student__semester__active",
        "exam",
        "student__semester",
    )
