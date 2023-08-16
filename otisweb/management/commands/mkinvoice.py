from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand

import core.models
import roster.models


class Command(BaseCommand):
    help = "Creates invoices for all the students in the active semester without an active invoice"

    def add_arguments(self, parser: ArgumentParser):
        _ = parser.add_argument("preps", type=int, help="Number of preps taught")

    def handle(self, *arg: Any, **options: Any):
        semester = core.models.Semester.objects.get(
            active=True
        )  # crash if > 1 semester
        students = roster.models.Student.objects.filter(
            semester=semester, invoice__isnull=True
        )

        invoices = [
            roster.models.Invoice(
                student=s,
                preps_taught=options["preps"],
            )
            for s in students
        ]
        print(f"Created {len(invoices)} invoices")
        roster.models.Invoice.objects.bulk_create(invoices)
