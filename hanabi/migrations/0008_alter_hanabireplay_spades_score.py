# Generated by Django 4.1.6 on 2023-02-15 21:43

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hanabi", "0007_hanabicontest_variant_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hanabireplay",
            name="spades_score",
            field=models.FloatField(
                blank=True, help_text="The number of spades obtained.", null=True
            ),
        ),
    ]
