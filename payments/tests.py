from django.conf import settings
from evans_django_tools.testsuite import EvanTestCase
from roster.factories import InvoiceFactory, StudentFactory


class PaymentTest(EvanTestCase):

    def test_invoice_standalone(self):
        alice = StudentFactory.create()
        checksum = alice.get_checksum(settings.INVOICE_HASH_KEY)

        self.assertGetDenied('payments-invoice', alice.pk, '?')
        self.login(alice)
        self.assertGetDenied('payments-invoice', alice.pk, '?')

        self.assertGetNotFound('payments-invoice', alice.pk, checksum)

        invoice = InvoiceFactory.create(student=alice)
        str(invoice)  # make sure __str__ is alive
        self.assertGet20X('payments-invoice', alice.pk, checksum)

    def test_config(self):
        self.assertPost40X('payments-config')
        resp = self.assertGet20X('payments-config')
        self.assertIn('publicKey', resp.json())

    def test_success(self):
        self.assertGet20X('payments-success')

    def test_cancelled(self):
        self.assertGet20X('payments-cancelled')
