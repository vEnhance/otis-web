# Generated by Django 3.2.8 on 2021-10-19 17:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0005_auto_20211019_1235'),
    ]

    operations = [
        migrations.AlterField(
            model_name='guess',
            name='score',
            field=models.FloatField(blank=True, help_text='The score for the guess, computed by the backend.', null=True),
        ),
    ]
