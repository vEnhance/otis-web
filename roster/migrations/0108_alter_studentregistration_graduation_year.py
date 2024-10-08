# Generated by Django 5.1.1 on 2024-09-17 03:43

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("roster", "0107_alter_unitinquiry_was_auto_processed"),
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
                    (2030, "Graduating in 2030"),
                    (2031, "Graduating in 2031"),
                    (2032, "Graduating in 2032"),
                    (2033, "Graduating in 2033"),
                    (2034, "Graduating in 2034"),
                    (2035, "Graduating in 2035"),
                    (2036, "Graduating in 2036"),
                    (2037, "Graduating in 2037"),
                    (2038, "Graduating in 2038"),
                    (2039, "Graduating in 2039"),
                    (2040, "Graduating in 2040"),
                    (2041, "Graduating in 2041"),
                    (2042, "Graduating in 2042"),
                    (2043, "Graduating in 2043"),
                    (2044, "Graduating in 2044"),
                    (2045, "Graduating in 2045"),
                    (2046, "Graduating in 2046"),
                    (2047, "Graduating in 2047"),
                ],
                help_text="Enter your expected graduation year",
            ),
        ),
    ]
