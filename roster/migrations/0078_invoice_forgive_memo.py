# Generated by Django 3.2.7 on 2021-10-13 17:01

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("roster", "0077_alter_studentregistration_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="forgive_memo",
            field=models.TextField(
                blank=True, help_text="Internal note to self about why forgive=True."
            ),
        ),
    ]
