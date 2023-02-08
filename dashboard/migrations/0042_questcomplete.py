# Generated by Django 3.2.6 on 2021-08-29 02:27

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("roster", "0071_remove_student_usemo_score"),
        ("dashboard", "0041_remove_pset_instructor_comments"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuestComplete",
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
                    "student",
                    models.ForeignKey(
                        help_text="Student obtaining this reward",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="roster.student",
                    ),
                ),
            ],
        ),
    ]
