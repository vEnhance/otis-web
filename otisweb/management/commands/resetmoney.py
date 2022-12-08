from typing import Any

import core.models
from django.core.management.base import BaseCommand
from payments.models import get_semester_invoices_with_annotations
from roster.models import Invoice


class Command(BaseCommand):
    help = "Resets the payment info for the active semester"

    def handle(self, *args: Any, **options: Any):
        del args
        del options
        semester = core.models.Semester.objects.get(active=True)  # crash if > 1 semester
        invoices = get_semester_invoices_with_annotations(semester)
        for inv in invoices:
            inv.total_paid = inv.stripe_total  # type: ignore
            inv.credits = inv.job_total  # type: ignore

        Invoice.objects.bulk_update(invoices, fields=('total_paid',), batch_size=25)
