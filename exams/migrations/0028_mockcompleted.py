# Generated by Django 3.2.8 on 2021-10-22 14:11

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("roster", "0001_squashed_0102_alter_studentregistration_agreement_form"),
        ("exams", "0027_auto_20210806_0955"),
    ]

    operations = [
        migrations.CreateModel(
            name="MockCompleted",
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
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="roster.student"
                    ),
                ),
                (
                    "test",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="exams.practiceexam",
                    ),
                ),
            ],
            options={
                "unique_together": {("student", "test")},
            },
        ),
    ]
