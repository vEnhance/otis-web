from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tubes", "0013_drop_year_participation_add_spoil_before"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="OIMEAttempt",
            new_name="OIMEFight",
        ),
    ]
