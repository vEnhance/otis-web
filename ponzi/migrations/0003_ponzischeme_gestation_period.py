import datetime

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ponzi", "0002_key_on_user_instead_of_student"),
    ]

    operations = [
        migrations.AddField(
            model_name="ponzischeme",
            name="gestation_period",
            field=models.DurationField(
                default=datetime.timedelta(days=14),
                help_text="How long a bid takes to reach its next tier",
            ),
            preserve_default=False,
        ),
    ]
