# Rewrites the stored INQ_* choice values of UnitPetition to PET_*.
#
# Both directions are plain UPDATEs over an explicit old <-> new mapping: no row
# is created or deleted, and a value outside the mapping is left alone rather
# than being coerced into some default. The two vocabularies are disjoint, so
# re-running a direction is a no-op.

from django.db import migrations

RENAMES = {
    "action_type": {
        "INQ_ACT_UNLOCK": "PET_ACT_UNLOCK",
        "INQ_ACT_APPEND": "PET_ACT_APPEND",
        "INQ_ACT_DROP": "PET_ACT_DROP",
        "INQ_ACT_LOCK": "PET_ACT_LOCK",
    },
    "status": {
        "INQ_ACC": "PET_ACC",
        "INQ_REJ": "PET_REJ",
        "INQ_NEW": "PET_NEW",
        "INQ_HOLD": "PET_HOLD",
        "INQ_CANC": "PET_CANC",
    },
}


def remap(apps, reverse: bool):
    UnitPetition = apps.get_model("roster", "UnitPetition")
    for field, mapping in RENAMES.items():
        for old, new in mapping.items():
            if reverse:
                old, new = new, old
            UnitPetition.objects.filter(**{field: old}).update(**{field: new})


def forwards(apps, schema_editor):
    del schema_editor
    remap(apps, reverse=False)


def backwards(apps, schema_editor):
    del schema_editor
    remap(apps, reverse=True)


class Migration(migrations.Migration):
    dependencies = [
        ("roster", "0119_rename_unitinquiry_unitpetition"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
