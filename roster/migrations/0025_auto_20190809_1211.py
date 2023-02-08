# Generated by Django 2.1.9 on 2019-08-09 17:11

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("roster", "0024_auto_20190327_1911"),
    ]

    operations = [
        migrations.AlterField(
            model_name="student",
            name="track",
            field=models.CharField(
                choices=[
                    ("A", "Weekly"),
                    ("B", "Biweekly"),
                    ("C", "Corr."),
                    ("E", "Ext."),
                    ("G", "Grad"),
                    ("N", "Not applicable"),
                ],
                max_length=5,
            ),
        ),
    ]
