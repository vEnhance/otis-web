# Generated by Django 4.1.5 on 2023-02-02 16:00

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hanabi", "0004_rename_spade_score_hanabireplay_spades_score"),
    ]

    operations = [
        migrations.AddField(
            model_name="hanabicontest",
            name="processed",
            field=models.BooleanField(
                default=False, help_text="Whether the results have been processed"
            ),
        ),
        migrations.AddField(
            model_name="hanabicontest",
            name="start_date",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                help_text="When the contest becomes visible.",
            ),
            preserve_default=False,
        ),
    ]
