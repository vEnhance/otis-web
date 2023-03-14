# Generated by Django 4.1.7 on 2023-03-14 00:19

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="OpalHunt",
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
                    "name",
                    models.CharField(
                        help_text="Display name for this hunt", max_length=128
                    ),
                ),
                ("slug", models.SlugField(max_length=32)),
                (
                    "active",
                    models.BooleanField(
                        help_text="Whether to highlight this hunt on the list."
                    ),
                ),
                ("start_date", models.DateTimeField(help_text="When the hunt begins.")),
                (
                    "author_signup_url",
                    models.URLField(help_text="Link to signup form for authors"),
                ),
                (
                    "author_signup_deadline",
                    models.DateTimeField(
                        help_text="Authors need to sign up by this date."
                    ),
                ),
                (
                    "author_draft_deadline",
                    models.DateTimeField(
                        help_text="Authors need to have drafts of their puzzles done by this date."
                    ),
                ),
            ],
        ),
    ]
