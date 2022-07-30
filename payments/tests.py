from django.conf import settings
from otisweb.tests import OTISTestCase
from roster.factories import InvoiceFactory, StudentFactory


class PaymentTest(OTISTestCase):
	def test_invoice_standalone(self):
		alice = StudentFactory.create()
		InvoiceFactory.create(student=alice)
		self.assertGet20X(
			'payments-invoice', alice.pk, alice.get_checksum(settings.INVOICE_HASH_KEY)
		)
		self.assertGetDenied('payments-invoice', alice.pk, '?')
		self.login(alice)
		self.assertGetDenied('payments-invoice', alice.pk, '?')
