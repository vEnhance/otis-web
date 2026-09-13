"""Checks that `fixtures/` still works against the current models.

A model gaining a non-nullable field breaks `loaddata` without breaking
anything else, because `loaddata` inserts raw rows and so never fires
`auto_now_add` and friends.
"""

import importlib.util
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.serializers import deserialize

from core.models import Semester
from dashboard.models import PSet
from roster.models import Student
from tubes.models import OIMEFight, OIMEProposal

FIXTURE_DIR = Path(settings.BASE_DIR) / "fixtures"
GEN_DUMMY_DATA_FIXTURES = ("core.UnitGroup", "core.Unit", "rpg.Level")


def load_fixtures(*names: str) -> None:
    """Loads fixtures by name and checks every object in them made it in."""
    paths = [FIXTURE_DIR / f"{name}.json" for name in names]
    call_command("loaddata", *paths, verbosity=0)

    wanted = Counter(
        obj.object._meta.label_lower
        for path in paths
        for obj in deserialize("json", path.read_text())
    )
    assert wanted
    for label, count in wanted.items():
        assert apps.get_model(label).objects.count() >= count, label


def import_populate() -> ModuleType:
    """Imports `fixtures/populate.py`, which is a script rather than a module."""
    spec = importlib.util.spec_from_file_location(
        "otis_populate", FIXTURE_DIR / "populate.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.django_db
def test_load_all():
    load_fixtures("all")


@pytest.mark.django_db
def test_load_gen_dummy_data_fixtures():
    load_fixtures(*GEN_DUMMY_DATA_FIXTURES)


@pytest.mark.django_db
def test_populate(monkeypatch: pytest.MonkeyPatch):
    load_fixtures(*GEN_DUMMY_DATA_FIXTURES)
    monkeypatch.setattr(sys, "argv", ["populate.py", "-s", "8", "-o", "6"])
    import_populate().main()

    assert Semester.objects.count() == 2
    assert Student.objects.count() == 4 + 5
    assert PSet.objects.exists()
    assert OIMEProposal.objects.count() == 6
    assert OIMEFight.objects.exists()
