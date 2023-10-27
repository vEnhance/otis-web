# Generated by Django 4.2.5 on 2023-10-26 01:26

from django.db import migrations, models


def set_difficulty_and_version(apps, schema_editor):
    Unit = apps.get_model("core", "unit")
    for unit in Unit.objects.all():
        unit.difficulty = unit.code[0]
        unit.version = unit.code[2]
        unit.save()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0057_userprofile_show_portal_instructions"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="unit",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="unit",
            name="difficulty",
            field=models.CharField(
                choices=[("B", "Easy/Bet"), ("D", "Medium/Dalet"), ("Z", "Hard/Zayin")],
                default="W",
                help_text="The difficulty code for the handout, like B",
                max_length=2,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="unit",
            name="version",
            field=models.CharField(
                choices=[("W", "W"), ("X", "X"), ("Y", "Y")],
                default="W",
                help_text="The version code for the handout, like W",
                max_length=2,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(set_difficulty_and_version),
        migrations.AlterUniqueTogether(
            name="unit",
            unique_together={("group", "difficulty", "version")},
        ),
        migrations.RemoveField(
            model_name="unit",
            name="code",
        ),
    ]
