from typing import Any

from django.core.management.base import BaseCommand
from django.db.models.functions.comparison import Coalesce
from sql_util.aggregates import SubquerySum

from roster.models import Invoice


class Command(BaseCommand):
    help = "Resets the total_paid for the active semester"

    def handle(self, *args: Any, **options: Any):
        del args
        del options

        invoices = Invoice.objects.filter(student__semester__active=True).annotate(
            stripe_total=Coalesce(SubquerySum("paymentlog__amount"), 0),
        )
        for inv in invoices:
            inv.total_paid = inv.stripe_total  # type: ignore

        Invoice.objects.bulk_update(invoices, fields=("total_paid",), batch_size=25)
