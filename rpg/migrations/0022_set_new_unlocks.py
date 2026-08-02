# Manual migration to retroactively mark the guesses that actually earned a
# diamond, as opposed to re-entering a code the user had already redeemed.
#
# A guess is the one that earned the diamond if the corresponding unlock was
# created no earlier than the guess itself: the view writes the guess first and
# the unlock immediately after, so a repeat redeem always postdates its unlock.

from django.db import migrations
from django.db.models import Exists, OuterRef


def set_new_unlocks(apps: object, schema_editor: object) -> None:
    AchievementCodeGuess = apps.get_model("rpg", "AchievementCodeGuess")  # type: ignore[attr-defined]
    AchievementUnlock = apps.get_model("rpg", "AchievementUnlock")  # type: ignore[attr-defined]

    granting_unlock = AchievementUnlock.objects.filter(
        user_id=OuterRef("user_id"),
        achievement_id=OuterRef("achievement_id"),
        timestamp__gte=OuterRef("timestamp"),
    )

    # Materialise the PKs in a plain SELECT first, mirroring 0019: keeping the
    # UPDATE free of subqueries avoids any surprises on MySQL.
    pks = list(
        AchievementCodeGuess.objects.filter(is_correct=True)
        .filter(Exists(granting_unlock))
        .values_list("pk", flat=True)
    )
    AchievementCodeGuess.objects.filter(pk__in=pks).update(is_new_unlock=True)


def unset_new_unlocks(apps: object, schema_editor: object) -> None:
    AchievementCodeGuess = apps.get_model("rpg", "AchievementCodeGuess")  # type: ignore[attr-defined]
    AchievementCodeGuess.objects.filter(is_new_unlock=True).update(is_new_unlock=False)


class Migration(migrations.Migration):
    dependencies = [
        ("rpg", "0021_achievementcodeguess_is_new_unlock"),
    ]

    operations = [
        migrations.RunPython(set_new_unlocks, reverse_code=unset_new_unlocks),
    ]
