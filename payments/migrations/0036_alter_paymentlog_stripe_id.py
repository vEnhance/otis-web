# Generated by Django 4.2.5 on 2023-09-23 15:13

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0035_paymentlog_stripe_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentlog",
            name="stripe_id",
            field=models.CharField(
                blank=True,
                help_text="Stripe payment intent identifier",
                max_length=120,
                verbose_name="Stripe payment intent ID",
            ),
        ),
    ]
