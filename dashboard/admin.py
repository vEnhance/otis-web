# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import PSet, SemesterDownloadFile, UploadedFile  # NOQA


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at",)
    list_display = (
        "pk",
        "content",
        "created_at",
        "description",
        "benefactor",
        "unit",
        "category",
        "owner",
    )
    search_fields = ("description",)
    list_filter = ("category",)
    list_per_page = 30
    autocomplete_fields = (
        "benefactor",
        "unit",
        "owner",
    )


@admin.register(SemesterDownloadFile)
class SemesterDownloadFileAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at",)
    list_display = (
        "pk",
        "semester",
        "content",
        "created_at",
        "description",
    )
    search_fields = ("description",)
    list_filter = ("semester",)
    list_per_page = 30


@admin.register(PSet)
class PSetAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "status",
        "student",
        "unit",
        "hours",
        "clubs",
    )
    search_fields = (
        "pk",
        "unit__group__name",
        "student__user__first_name",
        "student__user__last_name",
        "feedback",
        "special_notes",
    )
    list_filter = (
        "status",
        "student__semester",
        "eligible",
        "unit__group__subject",
    )
    list_display_links = (
        "pk",
        "status",
        "student",
        "unit",
    )
    list_per_page = 30
    autocomplete_fields = (
        "student",
        "unit",
    )

    def accept_pset(self, request: HttpRequest, queryset: QuerySet[PSet]):
        del request
        for pset in queryset:
            if pset.next_unit_to_unlock is not None:
                pset.student.unlocked_units.add(pset.next_unit_to_unlock)
            if pset.unit is not None:
                pset.student.unlocked_units.remove(pset.unit)
        queryset.update(status="A")

    def accept_pset_without_unlock(
        self, request: HttpRequest, queryset: QuerySet[PSet]
    ):
        del request
        queryset.update(status="A")

    def reject_pset(self, request: HttpRequest, queryset: QuerySet[PSet]):
        del request
        queryset.update(status="R")

    actions = [
        "accept_pset",
        "accept_pset_without_unlock",
        "reject_pset",
    ]
