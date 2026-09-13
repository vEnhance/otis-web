"""Checks that the JSON in `fixtures/` still loads against the current models.

A model gaining a non-nullable field breaks `loaddata` without breaking
anything else, because `loaddata` bypasses `auto_now_add` and friends.
"""

import pytest
from django.conf import settings
from django.core.management import call_command

from core.models import Unit, UnitGroup
from roster.models import Assistant
from rpg.models import Level

FIXTURE_DIR = settings.BASE_DIR / "fixtures"


@pytest.mark.django_db
def test_load_all():
    call_command("loaddata", FIXTURE_DIR / "all.json", verbosity=0)
    assert Assistant.objects.exists()


@pytest.mark.django_db
def test_load_gen_dummy_data_fixtures():
    call_command(
        "loaddata",
        FIXTURE_DIR / "core.UnitGroup.json",
        FIXTURE_DIR / "core.Unit.json",
        FIXTURE_DIR / "rpg.Level.json",
        verbosity=0,
    )
    assert UnitGroup.objects.exists()
    assert Unit.objects.exists()
    assert Level.objects.exists()
