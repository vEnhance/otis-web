# Replaces the legit/newborn/enabled booleans of Student with a single
# `standing` choice field, which has two values the booleans could not express:
# probation and suspension.  Existing rows only map onto the four old states.

from django.db import migrations, models


def set_standings(apps, schema_editor):
    del schema_editor
    Student = apps.get_model("roster", "Student")
    Student.objects.filter(legit=False).update(standing="STND_FAKE")
    legit = Student.objects.filter(legit=True)
    legit.filter(newborn=True).update(standing="STND_NEWB")
    legit.filter(newborn=False, enabled=True).update(standing="STND_GOOD")
    legit.filter(newborn=False, enabled=False).update(standing="STND_DROP")


def set_booleans(apps, schema_editor):
    del schema_editor
    Student = apps.get_model("roster", "Student")
    Student.objects.update(legit=True, newborn=False, enabled=True)
    Student.objects.filter(standing="STND_FAKE").update(legit=False)
    Student.objects.filter(standing="STND_NEWB").update(newborn=True)
    Student.objects.filter(standing__in=("STND_SUSP", "STND_DROP")).update(
        enabled=False
    )


class Migration(migrations.Migration):
    dependencies = [
        ("roster", "0122_studentregistration_us_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="student",
            name="standing",
            field=models.CharField(
                choices=[
                    ("STND_GOOD", "Good standing"),
                    ("STND_NEWB", "Newborn"),
                    ("STND_PROB", "Probation"),
                    ("STND_SUSP", "Suspended"),
                    ("STND_FAKE", "Fake account"),
                    ("STND_DROP", "Dropped"),
                ],
                default="STND_NEWB",
                help_text="The academic standing of this student.",
                max_length=9,
            ),
        ),
        migrations.RunPython(set_standings, reverse_code=set_booleans),
        migrations.RemoveField(
            model_name="student",
            name="enabled",
        ),
        migrations.RemoveField(
            model_name="student",
            name="legit",
        ),
        migrations.RemoveField(
            model_name="student",
            name="newborn",
        ),
        migrations.AlterModelOptions(
            name="student",
            options={
                "ordering": (
                    "semester",
                    models.Case(models.When(standing="STND_FAKE", then=1), default=0),
                    "user__first_name",
                    "user__last_name",
                )
            },
        ),
    ]
