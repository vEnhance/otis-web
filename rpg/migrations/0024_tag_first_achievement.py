from django.db import migrations


def tag_first_achievement(apps, schema_editor):
    Achievement = apps.get_model("rpg", "Achievement")
    if not Achievement.objects.filter(special_effect_id="first").exists():
        Achievement.objects.filter(pk=1, special_effect_id__isnull=True).update(
            special_effect_id="first"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("rpg", "0023_achievement_code_optional"),
    ]

    operations = [
        migrations.RunPython(tag_first_achievement, migrations.RunPython.noop),
    ]
