# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2017-08-05 23:37
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0001_squashed_0054_userprofile_use_twemoji"),
    ]

    operations = [
        migrations.CreateModel(
            name="Assignment",
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
                    "name",
                    models.CharField(
                        blank=True,
                        help_text="Name of the assignment; leave blank for mock olympiads",
                        max_length=80,
                        unique=True,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="MockOlympiad",
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
                    "family",
                    models.CharField(
                        choices=[
                            ("Waltz", "Waltz"),
                            ("Tango", "Tango"),
                            ("Foxtrot", "Foxtrot"),
                        ],
                        help_text="The family that the mock olympiad comes from",
                        max_length=10,
                    ),
                ),
                (
                    "number",
                    models.PositiveSmallIntegerField(
                        help_text="The number of the test (e.g. Waltz 8)"
                    ),
                ),
                (
                    "jmo_url",
                    models.CharField(
                        blank=True,
                        help_text="The URL to the JMO problems",
                        max_length=120,
                    ),
                ),
                (
                    "usamo_url",
                    models.CharField(
                        blank=True,
                        help_text="The URL to the USAMO problems",
                        max_length=120,
                    ),
                ),
                (
                    "solns_url",
                    models.CharField(
                        blank=True, help_text="The URL to the solutions", max_length=120
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="assignment",
            name="olympiad",
            field=models.ForeignKey(
                blank=True,
                help_text="If applicable, a PDF of the suitable mock olympiad",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="exams.MockOlympiad",
            ),
        ),
        migrations.AddField(
            model_name="assignment",
            name="semester",
            field=models.ForeignKey(
                help_text="The semester that the assignment is given in",
                on_delete=django.db.models.deletion.CASCADE,
                to="core.Semester",
            ),
        ),
    ]
