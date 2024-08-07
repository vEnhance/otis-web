# Generated by Django 4.1.10 on 2023-08-10 20:39

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import dashboard.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0001_squashed_0054_userprofile_use_twemoji"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("roster", "0001_squashed_0102_alter_studentregistration_agreement_form"),
    ]

    operations = [
        migrations.CreateModel(
            name="UploadedFile",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("psets", "PSet Submission"),
                            ("scripts", "Transcript"),
                            ("notes", "Notes / Comments"),
                            ("misc", "Miscellaneous"),
                        ],
                        help_text="What kind of file this is",
                        max_length=10,
                    ),
                ),
                (
                    "content",
                    models.FileField(
                        help_text="Upload your write-ups as PDF, TeX, TXT, PNG, or JPG. At most one file.",
                        upload_to=dashboard.models.content_file_name,
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                allowed_extensions=["pdf", "txt", "tex", "png", "jpg"]
                            )
                        ],
                        verbose_name="Your submission",
                    ),
                ),
                (
                    "benefactor",
                    models.ForeignKey(
                        help_text="The student for which this file is meant",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="roster.student",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        help_text="The user who uploaded the file",
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        blank=True,
                        help_text="The unit for which this file is associated",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="core.unit",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, default=django.utils.timezone.now
                    ),
                ),
                (
                    "description",
                    models.CharField(
                        blank=True,
                        help_text="Optional description of the file",
                        max_length=250,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="SemesterDownloadFile",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "description",
                    models.CharField(
                        blank=True,
                        help_text="Optional description of the file",
                        max_length=250,
                    ),
                ),
                (
                    "content",
                    models.FileField(
                        help_text="The file itself",
                        upload_to=dashboard.models.download_file_name,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "semester",
                    models.ForeignKey(
                        help_text="The semester to which the file is associated",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.semester",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="PSet",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "hours",
                    models.FloatField(
                        blank=True,
                        help_text="Number of hours (♥) spent on this problem set",
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(200),
                        ],
                        verbose_name="♥ Hours spent (estimate)",
                    ),
                ),
                (
                    "clubs",
                    models.IntegerField(
                        blank=True,
                        help_text="Total number of clubs (♣) that you solved, including 1♣ for feedback",
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(200),
                        ],
                        verbose_name="♣ Clubs earned",
                    ),
                ),
                (
                    "feedback",
                    models.TextField(
                        blank=True,
                        help_text="Any other feedback about the problem set",
                        verbose_name="Feedback on problem set, worth [1♣]",
                    ),
                ),
                (
                    "special_notes",
                    models.TextField(
                        blank=True,
                        help_text="If there's anything you need to say before we proceed",
                    ),
                ),
                (
                    "next_unit_to_unlock",
                    models.ForeignKey(
                        blank=True,
                        help_text="The unit you want to work on next (leave blank for none)",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="unblocking_psets",
                        to="core.unit",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        help_text="The student attached to this",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="roster.student",
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        help_text="The unit you want to submit for",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="core.unit",
                    ),
                ),
                (
                    "upload",
                    models.ForeignKey(
                        blank=True,
                        help_text="The associated upload file for this problem set",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="dashboard.uploadedfile",
                    ),
                ),
                (
                    "eligible",
                    models.BooleanField(
                        default=True, help_text="Whether to count this for leveling up"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("A", "Accepted"),
                            ("R", "Rejected"),
                            ("PA", "Pending (prev accepted)"),
                            ("PR", "Pending (prev rejected)"),
                            ("P", "Pending (new)"),
                        ],
                        default="P",
                        max_length=4,
                    ),
                ),
            ],
            options={
                "verbose_name": "PSet submission",
                "verbose_name_plural": "PSet submissions",
            },
        ),
        migrations.AddField(
            model_name="pset",
            name="staff_comments",
            field=models.TextField(
                blank=True, help_text="Comments by Evan on this problem set"
            ),
        ),
    ]
