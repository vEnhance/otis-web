# Generated by Django 4.2.7 on 2023-11-26 22:37

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("roster", "0103_alter_assistant_user_alter_invoice_created_at_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invoice",
            name="memo",
            field=models.TextField(
                blank=True, help_text="Any notes about this invoice."
            ),
        ),
    ]
