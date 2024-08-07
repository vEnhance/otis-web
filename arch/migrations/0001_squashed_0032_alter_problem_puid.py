# Generated by Django 4.1.10 on 2023-08-10 20:39

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0001_squashed_0054_userprofile_use_twemoji"),
    ]

    operations = [
        migrations.CreateModel(
            name="Problem",
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
                    "puid",
                    models.CharField(
                        help_text="Problem identifier, as printed in OTIS. Capital letters and digits only.",
                        max_length=20,
                        unique=True,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Only uppercase letters and digits appear in PUID's.",
                                regex="^[A-Z0-9]+$",
                            )
                        ],
                        verbose_name="PUID",
                    ),
                ),
                (
                    "hyperlink",
                    models.URLField(blank=True, help_text="An AoPS URL or similar"),
                ),
            ],
            options={
                "ordering": ("puid",),
            },
        ),
        migrations.CreateModel(
            name="Hint",
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
                    "keywords",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="A comma-separated list of keywords that a solver could look at to help them guess whether the hint is relevant or not. These are viewable immediately, so no spoilers here. Examples are 'setup', 'advice', 'answer confirmation', 'nudge','main idea', 'solution set', 'converse direction', 'construction', etc. Not all hints go well with keywords, so you can leave this blank if you can't think of anything useful to write.",
                        max_length=255,
                    ),
                ),
                (
                    "number",
                    models.PositiveIntegerField(
                        help_text="A number from 0 to 100 used to indicate an ordering for the hints. Here a number 0 means a hint given to someone at the very start whereas 100 means a hint given to someone who was read all previous hints or is close to the end of the problem. Do your best to make up an extrapolation for everything in between. A good idea is to give a sequence of hints with nearby numbers, say 20/21/22, each of which elaborates on the previous hint."
                    ),
                ),
                (
                    "content",
                    models.TextField(
                        help_text="The content of the hint. LaTeX rendering is okay."
                    ),
                ),
                (
                    "problem",
                    models.ForeignKey(
                        default=None,
                        help_text="The container of the current hint.",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="arch.problem",
                    ),
                ),
            ],
            options={
                "unique_together": {("problem", "number")},
            },
        ),
        migrations.CreateModel(
            name="Vote",
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
                    "niceness",
                    models.PositiveIntegerField(
                        help_text="A student submitted number from 0 to 10 used to indicate the approximate niceness of a problem.",
                        validators=[django.core.validators.MaxValueValidator(10)],
                    ),
                ),
                (
                    "problem",
                    models.ForeignKey(
                        help_text="The container of the current vote.",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="arch.problem",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="User who voted for this problem.",
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, default=django.utils.timezone.now
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
