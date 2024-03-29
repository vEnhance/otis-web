# Generated by Django 4.1.10 on 2023-08-10 23:33

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0055_alter_semester_end_year_alter_unit_group"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="use_twemoji",
            field=models.BooleanField(
                default=False,
                help_text="If the size of the spades emoji on meters bar is too small, enabling this feature will use twemoji to attempt to fix that.",
                verbose_name="Use Twemoji",
            ),
        ),
    ]
