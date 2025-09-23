from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0063_alter_userprofile_dynamic_progress_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="unitgroup",
            name="guest",
            field=models.BooleanField(
                default=False,
                help_text="Whether this unit is a guest unit.",
            ),
        ),
        migrations.AddField(
            model_name="unitgroup",
            name="guest_authors",
            field=models.CharField(
                max_length=255,
                blank=True,
                help_text="Comma-separated list of guest authors for this unit group.",
            ),
        ),
    ]





