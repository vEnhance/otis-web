# Generated by Django 5.0.7 on 2024-07-28 08:42

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import dashboard.models
import rpg.models


class Migration(migrations.Migration):
    replaces = [
        ("rpg", "0001_initial"),
        ("rpg", "0002_remove_achievement_active_remove_bonuslevel_active"),
        ("rpg", "0003_alter_questcomplete_category"),
        ("rpg", "0004_level_alttext"),
        ("rpg", "0005_achievement_show_solution"),
        ("rpg", "0006_alter_achievement_always_show_image_and_more"),
        ("rpg", "0007_achievement_show_creator"),
        ("rpg", "0008_vulnerabilityrecord"),
        ("rpg", "0009_alter_vulnerabilityrecord_options"),
        ("rpg", "0010_alter_achievement_code"),
        ("rpg", "0011_alter_achievement_id_alter_achievementunlock_id_and_more"),
        ("rpg", "0012_alter_achievement_table_and_more"),
        ("rpg", "0013_alter_achievement_id_alter_achievementunlock_id_and_more"),
    ]

    dependencies = [
        ("core", "0001_squashed_0054_userprofile_use_twemoji"),
        ("roster", "0001_squashed_0102_alter_studentregistration_agreement_form"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Achievement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "code",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=96,
                        unique=True,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="24-26 char hex string",
                                regex="^[a-f0-9]{24,26}$",
                            )
                        ],
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Name of the achievement", max_length=128
                    ),
                ),
                (
                    "image",
                    models.ImageField(
                        blank=True,
                        help_text="Image for the obtained achievement, at most 1MB.",
                        null=True,
                        upload_to=rpg.models.achievement_image_file_name,
                        validators=[dashboard.models.validate_at_most_1mb],
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Text shown beneath this achievement for students who obtain it.",
                    ),
                ),
                (
                    "solution",
                    models.TextField(
                        blank=True,
                        help_text="Description of where the diamond is hidden",
                    ),
                ),
                (
                    "diamonds",
                    models.SmallIntegerField(
                        default=0, help_text="Number of diamonds for this achievement"
                    ),
                ),
                (
                    "always_show_image",
                    models.BooleanField(
                        default=False,
                        help_text="If enabled, always show the achievement image, even if no one earned the diamond yet.",
                        verbose_name="Show Image",
                    ),
                ),
                (
                    "creator",
                    models.ForeignKey(
                        blank=True,
                        help_text="User who owns this achievement",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "show_solution",
                    models.BooleanField(
                        default=True,
                        help_text="If enabled, the solution page for a diamond is available to those who have unlocked the diamond.",
                        verbose_name="Show Solution",
                    ),
                ),
                (
                    "show_creator",
                    models.BooleanField(
                        default=False,
                        help_text="If enabled, the creator of a diamond is shown on the diamond page.",
                        verbose_name="Show Creator",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BonusLevel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "level",
                    models.PositiveSmallIntegerField(help_text="Level to spawn at"),
                ),
                (
                    "group",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE, to="core.unitgroup"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="AchievementUnlock",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "timestamp",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="The time the achievement was granted",
                    ),
                ),
                (
                    "achievement",
                    models.ForeignKey(
                        help_text="The achievement that was obtained",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="rpg.achievement",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="The user who unlocked the achievement",
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {("user", "achievement")},
            },
        ),
        migrations.CreateModel(
            name="BonusLevelUnlock",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                (
                    "bonus",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="rpg.bonuslevel"
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="roster.student"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Level",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "threshold",
                    models.IntegerField(
                        help_text="The number of the level", unique=True
                    ),
                ),
                (
                    "name",
                    models.CharField(help_text="The name of the level", max_length=128),
                ),
                (
                    "alttext",
                    models.TextField(
                        blank=True,
                        help_text="A memorable text that is displayed",
                        max_length=255,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PalaceCarving",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "display_name",
                    models.CharField(
                        help_text="How you would like your name to be displayed in the Ruby Palace.",
                        max_length=128,
                    ),
                ),
                (
                    "message",
                    models.TextField(
                        blank=True,
                        help_text="You can write a message here",
                        max_length=1024,
                    ),
                ),
                (
                    "hyperlink",
                    models.URLField(
                        blank=True, help_text="An external link of your choice"
                    ),
                ),
                (
                    "visible",
                    models.BooleanField(
                        default=True,
                        help_text="Uncheck to hide your carving altogether (can change your mind later)",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "image",
                    models.ImageField(
                        blank=True,
                        help_text="Optional small photo that will appear next to your carving, no more than 1 megabyte",
                        null=True,
                        upload_to=rpg.models.palace_image_file_name,
                        validators=[dashboard.models.validate_at_most_1mb],
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="QuestComplete",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(help_text="A summary", max_length=160)),
                (
                    "spades",
                    models.PositiveSmallIntegerField(
                        help_text="The number of spades granted"
                    ),
                ),
                (
                    "timestamp",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="The time the achievement was granted",
                    ),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("PR", "Pull request"),
                            ("BR", "Bug report"),
                            ("VD", "Vulnerability disclosure"),
                            ("WK", "Wiki bonus"),
                            ("US", "USEMO Score"),
                            ("UG", "USEMO Grading"),
                            ("MS", "Miscellaneous"),
                        ],
                        default="MS",
                        max_length=4,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        help_text="Student obtaining this reward",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="roster.student",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="VulnerabilityRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "commit_hash",
                    models.CharField(
                        help_text="The hash of the commit fixing the issue.",
                        max_length=64,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Needs to be a hex hash", regex="[0-9a-f]+"
                            )
                        ],
                    ),
                ),
                (
                    "timestamp",
                    models.DateField(help_text="Date to attach to the vulnerability."),
                ),
                (
                    "finder_name",
                    models.CharField(
                        blank=True, help_text="Person to attribute", max_length=80
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        help_text="A description of what was fixed by this commit."
                    ),
                ),
                (
                    "spades",
                    models.PositiveSmallIntegerField(
                        blank=True, help_text="The number of spades awarded.", null=True
                    ),
                ),
            ],
            options={
                "ordering": ("timestamp", "commit_hash"),
            },
        ),
    ]
