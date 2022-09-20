from django.conf import settings
from evans_django_tools.testsuite import EvanTestCase
from roster.factories import InvoiceFactory, StudentFactory


class PaymentTest(EvanTestCase):
	def test_invoice_standalone(self):
		alice = StudentFactory.create()
		invoice = InvoiceFactory.create(student=alice)
		str(invoice)  # make sure __str__ is alive

		self.assertGet20X(
			'payments-invoice', alice.pk, alice.get_checksum(settings.INVOICE_HASH_KEY)
		)
		self.assertGetDenied('payments-invoice', alice.pk, '?')
		self.login(alice)
		self.assertGetDenied('payments-invoice', alice.pk, '?')
