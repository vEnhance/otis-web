from typing import Any

import core.models
import roster.models
from django.core.management.base import BaseCommand
from django.db.models.aggregates import Sum
from django.db.models.expressions import OuterRef, Subquery
from django.db.models.functions.comparison import Coalesce


class Command(BaseCommand):
	help = "Resets the payment info for the active semester"

	def handle(self, *arg: Any, **options: Any):
		semester = core.models.Semester.objects.get(active=True)  # crash if > 1 semester
		invoices = roster.models.Invoice.objects.filter(student__semester=semester)

		queryset = invoices.filter(pk=OuterRef('pk'))
		queryset = queryset.annotate(total=Coalesce(Sum('paymentlog__amount'), 0))
		invoices.update(total_paid=Subquery(queryset.values('total')))
