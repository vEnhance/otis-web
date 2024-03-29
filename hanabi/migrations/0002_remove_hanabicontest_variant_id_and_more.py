# Generated by Django 4.1.5 on 2023-02-02 06:53

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hanabi", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="hanabicontest",
            name="variant_id",
        ),
        migrations.AddField(
            model_name="hanabicontest",
            name="num_suits",
            field=models.PositiveSmallIntegerField(
                default=5, help_text="The number of suits."
            ),
        ),
    ]
