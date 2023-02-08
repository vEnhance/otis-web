# Generated by Django 4.1.6 on 2023-02-08 20:30

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("arch", "0030_alter_vote_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vote",
            name="mohs",
            field=models.FloatField(
                help_text="A number from 0 to 50 used to indicate the approximate MOHS of a problem.",
                validators=[django.core.validators.MaxValueValidator(50)],
            ),
        ),
    ]
