from django.contrib import admin
from django.db.models.query import QuerySet
from django.http.request import HttpRequest
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import Job, JobFolder, PaymentLog, Worker


@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at",)
    list_display = (
        "invoice",
        "amount",
        "created_at",
    )
    list_filter = ("invoice__student__semester",)
    search_fields = (
        "invoice__student__user__first_name",
        "invoice__student__user__last_name",
        "invoice__student__user__username",
    )
    autocomplete_fields = ("invoice",)


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    readonly_fields = ("updated_at",)
    list_display = (
        "pk",
        "user",
        "full_name",
        "email",
        "updated_at",
        "notes",
    )
    list_display_links = (
        "pk",
        "user",
    )
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
        "gmail_address",
        "twitch_username",
        "paypal_username",
        "venmo_handle",
        "zelle_info",
    )
    autocomplete_fields = ("user",)


@admin.register(JobFolder)
class JobFolderAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "name",
        "slug",
        "visible",
        "max_pending",
        "max_total",
    )
    list_display_links = (
        "pk",
        "name",
        "slug",
    )
    list_filter = ("visible",)
    search_fields = ("name",)


class JobIEResource(resources.ModelResource):
    class Meta:
        skip_unchanged = True
        model = Job
        fields = (
            "id",
            "folder",
            "name",
            "description",
            "progress",
            "updated_at",
            "spades_bounty",
            "usd_bounty",
            "hours_estimate",
            "assignee",
            "assignee__user__first_name",
            "assignee__user__last_name",
            "assignee__user__email",
        )
        export_order = fields


@admin.register(Job)
class JobAdmin(ImportExportModelAdmin):
    def flagged(self, obj: Job) -> bool:
        return obj.admin_notes != ""

    flagged.boolean = True

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    list_display = (
        "pk",
        "name",
        "folder",
        "progress",
        "updated_at",
        "assignee",
        "assignee_name",
        "assignee_email",
        "flagged",
        "spades_bounty",
        "usd_bounty",
    )
    list_display_links = (
        "pk",
        "name",
        "folder",
        "progress",
    )
    search_fields = (
        "name",
        "description",
        "assignee__user__first_name",
        "assignee__user__last_name",
        "assignee__user__username",
    )
    list_filter = (
        ("assignee", admin.EmptyFieldListFilter),
        ("admin_notes", admin.EmptyFieldListFilter),
        "folder",
        "progress",
        "payment_preference",
    )
    autocomplete_fields = ("assignee",)

    resource_class = JobIEResource

    actions = [
        "unassign_job",
    ]

    def unassign_job(self, request: HttpRequest, queryset: QuerySet[Job]):
        del request
        queryset.update(progress="JOB_NEW", assignee=None)
