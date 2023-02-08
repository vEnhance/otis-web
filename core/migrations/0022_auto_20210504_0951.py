# Generated by Django 3.1.8 on 2021-05-04 13:51

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0021_auto_20210427_1624"),
    ]

    operations = [
        migrations.AddField(
            model_name="semester",
            name="first_payment_deadline",
            field=models.DateTimeField(
                blank=True, help_text="Deadline for nonzero payment.", null=True
            ),
        ),
        migrations.AddField(
            model_name="semester",
            name="most_payment_deadline",
            field=models.DateTimeField(
                blank=True,
                help_text="Deadline for two-thirds of the payment.",
                null=True,
            ),
        ),
    ]
