# Generated by Django 4.2.5 on 2023-09-23 06:02

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0034_remove_job_semester"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentlog",
            name="stripe_id",
            field=models.CharField(
                blank=True, help_text="Stripe payment ID", max_length=120
            ),
        ),
    ]
