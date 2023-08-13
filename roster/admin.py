from typing import Any, Optional, Tuple

from django.contrib import admin, messages
from django.contrib.admin.options import ModelAdmin
from django.contrib.auth.models import User
from django.db.models import F, FloatField, QuerySet
from django.db.models.base import Model
from django.db.models.functions import Cast
from django.http import HttpRequest
from django.utils import timezone
from import_export import fields, resources, widgets
from import_export.admin import ImportExportModelAdmin

from core.models import Semester, Unit

from .models import (  # NOQA
    Assistant,
    Invoice,
    RegistrationContainer,
    Student,
    StudentRegistration,
    UnitInquiry,
)


class RosterResource(resources.ModelResource):
    user_name = fields.Field(
        column_name="User Name",
        attribute="user",
        widget=widgets.ForeignKeyWidget(User, "username"),
    )


# ASSISTANT
class AssistantIEResource(RosterResource):
    class Meta:
        skip_unchanged = True
        model = Assistant
        fields = (
            "id",
            "user_name",
            "shortname",
            "user__first_name",
            "user__last_name",
        )
        export_order = fields


class StudentInline(admin.TabularInline):
    model = Student
    fk_name = "assistant"
    fields = (
        "name",
        "semester",
        "legit",
    )
    readonly_fields = (
        "user",
        "name",
        "semester",
    )
    extra = 0
    show_change_link = True

    def has_delete_permission(
        self, request: HttpRequest, obj: Optional[Student] = None
    ) -> bool:
        del request, obj
        return False


@admin.register(Assistant)
class AssistantAdmin(ImportExportModelAdmin):
    list_display = (
        "pk",
        "name",
        "shortname",
        "user",
    )
    list_display_links = ("name",)
    search_fields = ("user__first_name", "user__last_name", "user__username")
    autocomplete_fields = (
        "user",
        "unlisted_students",
    )
    inlines = (StudentInline,)
    resource_class = AssistantIEResource


# INVOICE
class InvoiceIEResource(resources.ModelResource):
    class Meta:
        skip_unchanged = True
        model = Invoice
        fields = (
            "id",
            "student",
            "student__user__first_name",
            "student__user__last_name",
            "student__user__email",
            "preps_taught",
            "hours_taught",
            "adjustment",
            "credits",
            "extras",
            "total_paid",
            "student__semester__name",
            "forgive_date",
            "memo",
        )
        export_order = fields


class OwedFilter(admin.SimpleListFilter):
    title = "remaining balance"
    parameter_name = "has_owed"

    def lookups(
        self,
        request: HttpRequest,
        model_admin: ModelAdmin[Any],
    ) -> list[Tuple[str, str]]:
        del request, model_admin
        return [
            ("incomplete", "Incomplete"),
            ("paid", "Paid in full"),
            ("excess", "Overpaid"),
            ("zero", "No payment"),
        ]

    def queryset(self, request: HttpRequest, queryset: QuerySet[Model]):
        del request
        if self.value() is None:
            return queryset
        queryset = queryset.annotate(
            owed=Cast(
                F("student__semester__prep_rate") * F("preps_taught")
                + F("student__semester__hour_rate") * F("hours_taught")
                + F("adjustment")
                + F("extras")
                - F("total_paid")
                - F("credits"),
                FloatField(),
            )
        )
        if self.value() == "incomplete":
            return queryset.filter(owed__gt=0)
        elif self.value() == "paid":
            return queryset.filter(owed__lte=0)
        elif self.value() == "excess":
            return queryset.filter(owed__lt=0)
        elif self.value() == "zero":
            return queryset.filter(owed__gt=0).filter(total_paid=0)


@admin.register(Invoice)
class InvoiceAdmin(ImportExportModelAdmin):
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    list_display = (
        "student",
        "total_owed",
        "total_cost",
        "forgive_date",
    )
    list_display_links = ("student",)
    search_fields = (
        "student__user__first_name",
        "student__user__last_name",
    )
    autocomplete_fields = ("student",)
    ordering = ("student",)
    list_filter = (
        OwedFilter,
        "student__legit",
        "student__semester__active",
        ("forgive_date", admin.EmptyFieldListFilter),
        "student__semester",
    )
    resource_class = InvoiceIEResource


# STUDENT
class StudentIEResource(RosterResource):
    semester_name = fields.Field(
        column_name="Semester Name",
        attribute="semester",
        widget=widgets.ForeignKeyWidget(Semester, "name"),
    )
    unit_list = fields.Field(
        column_name="Unit list",
        attribute="curriculum",
        widget=widgets.ManyToManyWidget(Unit, separator=";"),
    )

    class Meta:
        skip_unchanged = True
        model = Student
        fields = (
            "id",
            "user__first_name",
            "user__last_name",
            "user__email",
            "semester_name",
            "user_name",
            "legit",
        )
        export_order = fields


class UnlistedInline(admin.TabularInline):
    model = Student.unlisted_assistants.through  # type: ignore
    verbose_name = "Unlisted Assistant"
    verbose_name_plural = "Unlisted Assistants"
    extra = 0


class InvoiceInline(admin.StackedInline):
    model = Invoice
    fields = (
        "preps_taught",
        "hours_taught",
        "extras",
        "adjustment",
        "credits",
        "total_paid",
        "forgive_date",
        "memo",
    )
    readonly_fields = (
        "student",
        "pk",
    )


@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin):
    list_display = (
        "pk",
        "name",
        "semester",
        "enabled",
        "legit",
    )
    list_display_links = (
        "pk",
        "name",
        "semester",
    )
    list_filter = (
        "semester__active",
        "legit",
        "enabled",
        "newborn",
        "semester",
    )
    search_fields = (
        "pk",
        "user__first_name",
        "user__last_name",
        "user__username",
    )
    autocomplete_fields = (
        "user",
        "assistant",
        "curriculum",
        "unlocked_units",
    )
    inlines = (
        InvoiceInline,
        UnlistedInline,
    )
    resource_class = StudentIEResource


# REG FORM
class StudentRegistrationIEResource(RosterResource):
    class Meta:
        model = StudentRegistration
        fields = (
            "id",
            "user__first_name",
            "user__last_name",
            "user__email",
            "user_name",
            "container__semester__name",
            "processed",
            "parent_email",
            "country",
            "gender",
            "graduation_year",
            "school_name",
            "aops_username",
        )
        export_order = fields


def build_students(queryset: QuerySet[StudentRegistration]) -> int:
    students_to_create = []
    queryset = queryset.filter(container__semester__active=True)
    queryset = queryset.exclude(processed=True)
    queryset = queryset.select_related("user", "container", "container__semester")

    count = 0
    n = 0
    for registration in queryset:
        students_to_create.append(
            Student(
                user=registration.user,
                semester=registration.container.semester,
                reg=registration,
            )
        )

        semester_date = registration.container.semester.one_semester_date

        n = 1 if semester_date is not None and timezone.now() > semester_date else 2
        count += 1
    Student.objects.bulk_create(students_to_create)
    queryset.update(processed=True)

    if n > 0:
        invoices_to_create = []
        for student in Student.objects.filter(
            invoice__isnull=True, semester__active=True
        ):
            invoice = Invoice(student=student, preps_taught=n)

            invoices_to_create.append(invoice)
        Invoice.objects.bulk_create(invoices_to_create)
    return count


@admin.register(StudentRegistration)
class StudentRegistrationAdmin(ImportExportModelAdmin):
    readonly_fields = ("created_at",)
    list_display = (
        "name",
        "processed",
        "container",
        "about",
        "country",
        "agreement_form",
    )
    list_filter = (
        "container__semester",
        "processed",
        "gender",
        "graduation_year",
        "country",
    )
    list_display_links = (
        "name",
        "container",
    )
    resource_class = StudentRegistrationIEResource
    search_fields = ("user__first_name", "user__last_name")

    actions = [
        "create_student",
    ]

    def create_student(
        self, request: HttpRequest, queryset: QuerySet[StudentRegistration]
    ):
        num_built = build_students(queryset)
        messages.success(request, message=f"Built {num_built} students")


# INQUIRY
@admin.register(UnitInquiry)
class UnitInquiryAdmin(admin.ModelAdmin):
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    list_display = (
        "pk",
        "status",
        "action_type",
        "unit",
        "student",
        "explanation",
    )
    list_filter = (
        "status",
        "action_type",
        "student__assistant",
    )
    search_fields = (
        "student__user__first_name",
        "student__user__last_name",
        "student__user__username",
    )
    list_display_links = ("pk",)
    autocomplete_fields = (
        "unit",
        "student",
    )

    actions = ["hold_petition", "reject_petition", "accept_petition", "reset_petition"]

    def hold_petition(self, request: HttpRequest, queryset: QuerySet[UnitInquiry]):
        del request
        queryset.update(status="INQ_HOLD")

    def reject_petition(self, request: HttpRequest, queryset: QuerySet[UnitInquiry]):
        del request
        queryset.update(status="INQ_REJ")

    def accept_petition(self, request: HttpRequest, queryset: QuerySet[UnitInquiry]):
        del request
        for inquiry in queryset:
            inquiry.run_accept()

    def reset_petition(self, request: HttpRequest, queryset: QuerySet[UnitInquiry]):
        del request
        queryset.update(status="INQ_NEW")


# REGISTRATION
@admin.register(RegistrationContainer)
class RegistrationContainerAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "semester",
        "passcode",
        "accepting_responses",
    )
    list_display_links = (
        "pk",
        "semester",
    )
