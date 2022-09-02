from typing import Any

import core.models
import roster.models
from django.core.management.base import BaseCommand
from django.db.models.functions.comparison import Coalesce
from roster.models import Invoice
from sql_util.aggregates import SubquerySum


class Command(BaseCommand):
	help = "Resets the payment info for the active semester"

	def handle(self, *arg: Any, **options: Any):
		semester = core.models.Semester.objects.get(active=True)  # crash if > 1 semester
		invoices = roster.models.Invoice.objects.filter(student__semester=semester)
		invoices = invoices.annotate(stripe_total=Coalesce(SubquerySum('paymentlog__amount'), 0))

		for inv in invoices:
			inv.total_paid = inv.stripe_total

		Invoice.objects.bulk_update(invoices, fields=('total_paid', ), batch_size=25)
