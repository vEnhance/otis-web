# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-04-23 20:34
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_semester_registration_open'),
    ]

    operations = [
        migrations.CreateModel(
            name='UnitGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text="The display name for the handout, like 'Weird Geo'", max_length=255, unique=True)),
                ('description', models.TextField(help_text='A description of what this unit is')),
                ('subject', models.CharField(choices=[('A', 'Algebra'), ('C', 'Combinatorics'), ('G', 'Geometry'), ('N', 'Number Theory'), ('F', 'Functional Equations'), ('M', 'Miscellaneous')], help_text='The subject for the unit', max_length=2)),
            ],
        ),
        migrations.AddField(
            model_name='unit',
            name='group',
            field=models.ForeignKey(help_text='The group that this unit belongs to', null=True, on_delete=django.db.models.deletion.CASCADE, to='core.UnitGroup'),
        ),
        migrations.AlterUniqueTogether(
            name='unit',
            unique_together={('group', 'code')},
        ),
        migrations.RemoveField(
            model_name='unit',
            name='name',
        ),
        migrations.RemoveField(
            model_name='unit',
            name='subject',
        ),
    ]
