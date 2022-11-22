from django.conf import settings
from evans_django_tools.testsuite import EvanTestCase
from roster.factories import InvoiceFactory, StudentFactory

from payments.models import PaymentLog

from .views import process_payment


class PaymentTest(EvanTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alice = StudentFactory.create(user__username='alice')
        cls.invoice = InvoiceFactory.create(student=cls.alice)
        cls.checksum = cls.alice.get_checksum(settings.INVOICE_HASH_KEY)

    def test_invoice_standalone(self):
        self.assertGetDenied('payments-invoice', PaymentTest.alice.pk, '?')
        self.login(PaymentTest.alice)
        self.assertGetDenied('payments-invoice', PaymentTest.alice.pk, '?')
        str(PaymentTest.invoice)  # make sure __str__ is alive
        self.assertGet20X('payments-invoice', self.alice.pk, PaymentTest.checksum)

        bob = StudentFactory.create(user__username='bob')
        self.assertGetNotFound('payments-invoice', bob.pk,
                                bob.get_checksum(settings.INVOICE_HASH_KEY))

    def test_config(self):
        self.assertPost40X('payments-config')
        resp = self.assertGet20X('payments-config')
        self.assertIn('publicKey', resp.json())

    def test_checkout(self):
        pk = PaymentTest.invoice.pk
        self.assertPost40X('payments-checkout', pk, 240)
        self.assertGet40X('payments-checkout', pk, 0)  # amount >= 0

        resp = self.assertGet20X('payments-checkout', pk, 480)
        self.assertIn('sessionId', resp.json())

    def test_process_payment(self):
        process_payment(300, PaymentTest.invoice)
        self.assertEqual(PaymentTest.invoice.total_owed, 180)
        log = PaymentLog.objects.get()
        self.assertEqual(log.invoice.pk, PaymentTest.invoice.pk)
        self.assertEqual(log.amount, 300)

    def test_webhook(self):
        self.assertGet40X('payments-webhook')
        self.assertPost40X('payments-webhook')
        self.assertPost40X('payments-webhook', HTTP_STRIPE_SIGNATURE="meow")

    def test_success(self):
        self.assertGet20X('payments-success')

    def test_cancelled(self):
        self.assertGet20X('payments-cancelled')
