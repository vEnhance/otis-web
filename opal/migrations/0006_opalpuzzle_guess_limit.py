# Generated by Django 5.0.7 on 2024-07-29 18:45

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("opal", "0005_opalpuzzle_achievement"),
    ]

    operations = [
        migrations.AddField(
            model_name="opalpuzzle",
            name="guess_limit",
            field=models.PositiveSmallIntegerField(
                default=20, help_text="Maximum number of guesses to allow"
            ),
        ),
    ]
