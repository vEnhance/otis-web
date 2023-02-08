# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2017-08-05 23:43
from __future__ import unicode_literals

import datetime

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("exams", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="assignment",
            name="due_date",
            field=models.DateField(
                default=datetime.date(2017, 6, 3),
                help_text="When the assignment is due",
            ),
            preserve_default=False,
        ),
    ]
