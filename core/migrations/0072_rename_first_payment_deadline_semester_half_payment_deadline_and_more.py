from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0071_alter_semester_first_payment_deadline_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="semester",
            old_name="first_payment_deadline",
            new_name="half_payment_deadline",
        ),
        migrations.RenameField(
            model_name="semester",
            old_name="most_payment_deadline",
            new_name="full_payment_deadline",
        ),
    ]
