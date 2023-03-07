# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import datetime
import os
from typing import Optional

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import File
from django.core.validators import (  # NOQA
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.urls import reverse

from core.models import Semester, Unit
from roster.models import Student


def validate_at_most_1mb(f: File):  # type: ignore
    if f.size > 1024 * 1024:
        raise ValidationError("At most 1MB allowed")


def content_file_name(instance: "UploadedFile", filename: str) -> str:
    now = datetime.datetime.now()
    return os.path.join(
        instance.category,
        instance.owner.username,
        now.strftime("%Y-%m-%d-%H%M%S"),
        filename,
    )


class UploadedFile(models.Model):
    """An uploaded file, for example a transcript or homework solutions."""

    CHOICES = (
        ("psets", "PSet Submission"),
        ("scripts", "Transcript"),
        ("notes", "Notes / Comments"),
        ("misc", "Miscellaneous"),
    )
    benefactor = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        help_text="The student for which this file is meant",
    )
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, help_text="The user who uploaded the file"
    )
    category = models.CharField(
        max_length=10, choices=CHOICES, help_text="What kind of file this is"
    )
    description = models.CharField(
        max_length=250, blank=True, help_text="Optional description of the file"
    )
    content = models.FileField(
        verbose_name="Your submission",
        help_text="Upload your write-ups as PDF, TeX, TXT, PNG, or JPG. At most one file.",
        upload_to=content_file_name,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["pdf", "txt", "tex", "png", "jpg"]
            )
        ],
    )
    unit = models.ForeignKey(
        Unit,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="The unit for which this file is associated",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.filename

    def get_absolute_url(self):
        return self.url

    @property
    def filename(self):
        return os.path.basename(self.content.name)

    @property
    def url(self):
        return self.content.url


def download_file_name(instance: "SemesterDownloadFile", filename: str) -> str:
    return os.path.join("global", str(instance.semester.pk), filename)


class SemesterDownloadFile(models.Model):
    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        help_text="The semester to which the file is associated",
    )
    description = models.CharField(
        max_length=250, blank=True, help_text="Optional description of the file"
    )
    content = models.FileField(
        help_text="The file itself",
        upload_to=download_file_name,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return os.path.basename(self.content.name)

    def get_absolute_url(self):
        return self.content.url


class PSet(models.Model):
    status = models.CharField(
        max_length=4,
        choices=(
            ("A", "Accepted"),
            ("R", "Rejected"),
            ("PA", "Pending (prev accepted)"),
            ("PR", "Pending (prev rejected)"),
            ("P", "Pending (new)"),
        ),
        default="P",
    )
    student = models.ForeignKey(
        Student, help_text="The student attached to this", on_delete=models.CASCADE
    )
    unit = models.ForeignKey(
        Unit,
        help_text="The unit you want to submit for",
        on_delete=models.SET_NULL,
        null=True,
    )
    upload = models.ForeignKey(
        UploadedFile,
        help_text="The associated upload file for this problem set",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    hours = models.FloatField(
        help_text="Number of hours (♥) spent on this problem set",
        verbose_name="♥ Hours spent (estimate)",
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(200)],
    )
    clubs = models.IntegerField(
        help_text="Total number of clubs (♣) that you solved, including 1♣ for feedback",
        verbose_name="♣ Clubs earned",
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(200)],
    )
    eligible = models.BooleanField(
        default=True, help_text="Whether to count this for leveling up"
    )
    feedback = models.TextField(
        verbose_name="Feedback on problem set, worth [1♣]",
        help_text="Any other feedback about the problem set",
        blank=True,
    )
    next_unit_to_unlock = models.ForeignKey(
        Unit,
        help_text="The unit you want to work on next (leave blank for none)",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unblocking_psets",
    )
    special_notes = models.TextField(
        help_text="If there's anything you need to say before we proceed", blank=True
    )
    comments = models.TextField(
        help_text="Comments by Evan on this Unit Set",
        blank=True,
    )

    class Meta:
        verbose_name = "PSet submission"
        verbose_name_plural = "PSet submissions"

    def __str__(self):
        return f"{self.student.name} submits {self.unit}"

    def get_absolute_url(self):
        return reverse("pset", args=(self.pk,))

    @property
    def filename(self) -> Optional[str]:
        if self.upload is not None:
            return self.upload.filename
        else:
            return None

    @property
    def accepted(self) -> bool:
        return self.status == "A"

    @property
    def rejected(self) -> bool:
        return self.status == "R"

    @property
    def pending(self) -> bool:
        return not (self.accepted or self.rejected)

    @property
    def resubmitted(self) -> bool:
        return self.status in ("PA", "PR")
