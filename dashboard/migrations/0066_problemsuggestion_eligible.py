# Generated by Django 3.2.8 on 2021-10-22 14:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0065_alter_questcomplete_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='problemsuggestion',
            name='eligible',
            field=models.BooleanField(default=True, help_text='Whether this suggestion is eligible for spades.'),
        ),
    ]
