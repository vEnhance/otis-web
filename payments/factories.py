from factory.django import DjangoModelFactory
from factory.declarations import SubFactory
from payments.models import PaymentLog
from roster.factories import InvoiceFactory


class PaymentLogFactory(DjangoModelFactory):
	class Meta:
		model = PaymentLog

	invoice = SubFactory(InvoiceFactory)
	amount = 0
