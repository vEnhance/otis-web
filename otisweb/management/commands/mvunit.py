from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand

from core.models import Unit
from dashboard.models import UploadedFile
from roster.models import Student


class Command(BaseCommand):
    help = "Replaces all instances of unit X with unit Y"

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("source", type=int, help="pk of source unit")
        parser.add_argument("dest", type=int, help="pk of destination unit")

    def handle(self, *args: Any, **options: Any):
        source_pk = options.pop("source")
        dest_pk = options.pop("dest")
        print(f"Deleting {Unit.objects.get(pk=source_pk)}")
        print(f"Replacing with {Unit.objects.get(pk=dest_pk)}")

        u = UploadedFile.objects.filter(unit=source_pk)
        s1 = Student.objects.filter(curriculum=source_pk)
        s2 = Student.objects.filter(unlocked_units=source_pk)

        print(f"This will change {u.count()} uploaded files.")
        print(
            f"This will affect {s1.count()} students with the unit, of which {s2.count()} have it unlocked."
        )

        if input("Are you sure? ").strip().lower() != "y":
            return

        u.update(unit=dest_pk)
        for s in s1:
            s.curriculum.remove(source_pk)
            s.curriculum.add(dest_pk)
        for s in s2:
            s.unlocked_units.remove(source_pk)
            s.unlocked_units.add(dest_pk)
