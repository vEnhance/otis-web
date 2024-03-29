# Generated by Django 4.1.6 on 2023-02-03 05:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hanabi", "0006_alter_hanabicontest_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="hanabicontest",
            name="variant_id",
            field=models.PositiveIntegerField(
                default=0, help_text="The variant ID on hanab.live"
            ),
            preserve_default=False,
        ),
    ]
