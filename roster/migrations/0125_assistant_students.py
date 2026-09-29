from django.db import migrations, models


def fk_to_m2m(apps, schema_editor):
    Student = apps.get_model("roster", "Student")
    Through = apps.get_model("roster", "Assistant").students.through
    existing = set(Through.objects.values_list("assistant_id", "student_id"))
    Through.objects.bulk_create(
        Through(assistant_id=assistant_id, student_id=student_id)
        for student_id, assistant_id in Student.objects.filter(
            assistant__isnull=False
        ).values_list("pk", "assistant_id")
        if (assistant_id, student_id) not in existing
    )


def m2m_to_fk(apps, schema_editor):
    Student = apps.get_model("roster", "Student")
    Through = apps.get_model("roster", "Assistant").students.through
    for row in Through.objects.order_by("-pk"):
        Student.objects.filter(pk=row.student_id).update(assistant_id=row.assistant_id)


class Migration(migrations.Migration):
    dependencies = [
        ("roster", "0124_alter_invoice_forgive_date"),
    ]

    operations = [
        migrations.RenameField(
            model_name="assistant",
            old_name="unlisted_students",
            new_name="students",
        ),
        migrations.AlterField(
            model_name="assistant",
            name="students",
            field=models.ManyToManyField(
                blank=True,
                help_text="The students this assistant teaches.",
                related_name="assistants",
                to="roster.student",
            ),
        ),
        migrations.RunPython(fk_to_m2m, m2m_to_fk),
        migrations.RemoveField(
            model_name="student",
            name="assistant",
        ),
    ]
