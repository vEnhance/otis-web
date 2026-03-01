# Manual migration to retroactively mark the first non-creator AchievementUnlock
# for each Achievement as is_first_obtain=True.

from django.db import migrations


def set_first_obtains(apps: object, schema_editor: object) -> None:
    AchievementUnlock = apps.get_model("rpg", "AchievementUnlock")  # type: ignore[attr-defined]
    Achievement = apps.get_model("rpg", "Achievement")  # type: ignore[attr-defined]

    for achievement in Achievement.objects.all():
        # Find the earliest unlock that was not by the achievement's creator.
        first_unlock = (
            AchievementUnlock.objects.filter(achievement=achievement)
            .exclude(user=achievement.creator)
            .order_by("timestamp")
            .first()
        )
        if first_unlock is not None:
            first_unlock.is_first_obtain = True
            first_unlock.save(update_fields=["is_first_obtain"])


def unset_first_obtains(apps: object, schema_editor: object) -> None:
    AchievementUnlock = apps.get_model("rpg", "AchievementUnlock")  # type: ignore[attr-defined]
    AchievementUnlock.objects.filter(is_first_obtain=True).update(is_first_obtain=False)


class Migration(migrations.Migration):
    dependencies = [
        ("rpg", "0017_achievementunlock_is_first_obtain"),
    ]

    operations = [
        migrations.RunPython(set_first_obtains, reverse_code=unset_first_obtains),
    ]
