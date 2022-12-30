from django.contrib import admin

from .models import PaymentLog, Worker, Job, JobFolder
from import_export import resources
from import_export.admin import ImportExportModelAdmin


@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
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
    list_display = (
        "pk",
        "user",
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
            "name",
            "status",
            "folder",
            "updated_at",
            "spades_bounty",
            "usd_bounty",
            "assignee",
            "assignee__user__first_name",
            "assignee__user__last_name",
            "assignee__user__email",
        )


@admin.register(Job)
class JobAdmin(ImportExportModelAdmin):
    list_display = (
        "pk",
        "name",
        "folder",
        "status",
        "updated_at",
        "assignee",
        "assignee_name",
        "spades_bounty",
        "usd_bounty",
    )
    list_display_links = (
        "pk",
        "status",
        "name",
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
        "folder",
        "progress",
        "payment_preference",
    )
    autocomplete_fields = ("assignee",)
