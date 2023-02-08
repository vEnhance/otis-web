# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-08-13 15:37
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_unit_subject"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("roster", "0009_auto_20170808_1730"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="assistant",
            unique_together={("user", "semester")},
        ),
        migrations.AlterUniqueTogether(
            name="student",
            unique_together={("user", "semester")},
        ),
    ]
