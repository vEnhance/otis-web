# Renames UnitInquiry -> UnitPetition.
#
# RenameModel issues an ALTER TABLE ... RENAME, so every row is carried over
# untouched; it must never be replaced by a CreateModel/DeleteModel pair (which
# is what makemigrations autodetects here, since the choices changed at the same
# time). The choice *values* stored in action_type and status are remapped
# separately in 0120, which runs immediately after this one.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("roster", "0118_applyuuid_applicant_name_applyuuid_memo"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="UnitInquiry",
            new_name="UnitPetition",
        ),
        migrations.AlterField(
            model_name="unitpetition",
            name="action_type",
            field=models.CharField(
                choices=[
                    ("PET_ACT_UNLOCK", "Unlock now"),
                    ("PET_ACT_APPEND", "Add for later"),
                    ("PET_ACT_DROP", "Drop"),
                    ("PET_ACT_LOCK", "Lock (Drop + Add for later)"),
                ],
                help_text="Describe the action you want to make.",
                max_length=15,
            ),
        ),
        migrations.AlterField(
            model_name="unitpetition",
            name="status",
            field=models.CharField(
                choices=[
                    ("PET_ACC", "Accepted"),
                    ("PET_REJ", "Rejected"),
                    ("PET_NEW", "Pending"),
                    ("PET_HOLD", "On hold"),
                    ("PET_CANC", "Canceled"),
                ],
                default="PET_NEW",
                help_text="The current status of the petition.",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="unitpetition",
            name="was_auto_processed",
            field=models.BooleanField(
                default=False,
                help_text="Whether the petition was automatically accepted or rejected by auto-criteria.",
                verbose_name="Auto",
            ),
        ),
    ]
