# Manual migration to retroactively mark the first non-creator AchievementUnlock
# for each Achievement as is_first_obtain=True.
#
# Uses a single correlated subquery so the entire operation is O(1) DB queries
# regardless of how many achievements exist.

from django.db import migrations
from django.db.models import F, OuterRef, Subquery


def set_first_obtains(apps: object, schema_editor: object) -> None:
    AchievementUnlock = apps.get_model("rpg", "AchievementUnlock")  # type: ignore[attr-defined]

    # For each AchievementUnlock row, this subquery returns the pk of the earliest
    # non-creator unlock for the same achievement.  "Non-creator" means either the
    # achievement has no creator, or the unlock's user is not the achievement's creator.
    earliest_non_creator = (
        AchievementUnlock.objects.filter(achievement_id=OuterRef("achievement_id"))
        .exclude(achievement__creator=F("user"))
        .order_by("timestamp", "pk")
        .values("pk")[:1]
    )

    # Materialise the PKs in a plain SELECT first.  MySQL forbids referencing
    # the target table of an UPDATE inside a subquery (error 1093), so we
    # cannot do the UPDATE and the correlated subquery in a single statement.
    # Fetching IDs first (SELECT) has no such restriction.
    pks = list(
        AchievementUnlock.objects.filter(pk=Subquery(earliest_non_creator)).values_list(
            "pk", flat=True
        )
    )
    AchievementUnlock.objects.filter(pk__in=pks).update(is_first_obtain=True)


def unset_first_obtains(apps: object, schema_editor: object) -> None:
    AchievementUnlock = apps.get_model("rpg", "AchievementUnlock")  # type: ignore[attr-defined]
    AchievementUnlock.objects.filter(is_first_obtain=True).update(is_first_obtain=False)


class Migration(migrations.Migration):
    dependencies = [
        ("rpg", "0018_achievementunlock_is_first_obtain"),
    ]

    operations = [
        migrations.RunPython(set_first_obtains, reverse_code=unset_first_obtains),
    ]
