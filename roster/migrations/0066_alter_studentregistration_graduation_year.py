# Generated by Django 3.2.6 on 2021-08-12 18:36

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("roster", "0065_alter_studentregistration_agreement_form"),
    ]

    operations = [
        migrations.AlterField(
            model_name="studentregistration",
            name="graduation_year",
            field=models.IntegerField(
                choices=[
                    (0, "Already graduated high school"),
                    (2021, "Graduating in 2021"),
                    (2022, "Graduating in 2022"),
                    (2023, "Graduating in 2023"),
                    (2024, "Graduating in 2024"),
                    (2025, "Graduating in 2025"),
                    (2026, "Graduating in 2026"),
                    (2027, "Graduating in 2027"),
                    (2028, "Graduating in 2028"),
                    (2029, "Graduating in 2029"),
                ],
                help_text="Enter your expected graduation year",
            ),
        ),
    ]
