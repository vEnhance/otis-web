from hashlib import sha256

from arch.models import Hint
from core.factories import UnitFactory
from dashboard.factories import PSetFactory
from django.test.utils import override_settings
from otisweb.tests import OTISTestCase
from payments.factories import PaymentLogFactory
from roster.factories import InvoiceFactory, StudentFactory, UnitInquiryFactory
from roster.models import Invoice

EXAMPLE_PASSWORD = 'take just the first 24'
TARGET_HASH = sha256(EXAMPLE_PASSWORD.encode('ascii')).hexdigest()


@override_settings(API_TARGET_HASH=TARGET_HASH)
class TestVenueQAPI(OTISTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		alice = StudentFactory.create(user__first_name="Alice", user__last_name="Aardvárk")
		bob = StudentFactory.create(user__first_name="Bôb B.", user__last_name="Bèta")
		carol = StudentFactory.create(user__first_name="Carol", user__last_name="Cutie")
		david = StudentFactory.create(user__first_name="David", user__last_name="Darling")
		eve = StudentFactory.create(user__first_name="Eve", user__last_name="Edgeworth")

		submitted_unit, requested_unit = UnitFactory.create_batch(2)
		PSetFactory.create(
			student=alice,
			unit=submitted_unit,
			next_unit_to_unlock=requested_unit,
			clubs=120,
			hours=37,
			approved=False,
			feedback="Meow",
			special_notes="Purr",
		)
		PSetFactory.create(student=alice, approved=True)
		UnitInquiryFactory.create_batch(5, student=alice, action_type="UNLOCK", status="ACC")
		UnitInquiryFactory.create_batch(2, student=alice, action_type="DROP", status="ACC")
		UnitInquiryFactory.create_batch(3, student=alice, action_type="UNLOCK", status="NEW")

		alice.curriculum.add(submitted_unit)
		alice.curriculum.add(requested_unit)
		alice.unlocked_units.add(submitted_unit)

		InvoiceFactory.create(student=alice)
		InvoiceFactory.create(student=bob)
		invC = InvoiceFactory.create(student=carol)
		invD = InvoiceFactory.create(student=david)
		invE = InvoiceFactory.create(student=eve)
		PaymentLogFactory.create(invoice=invC, amount=50)
		PaymentLogFactory.create(invoice=invC, amount=70)
		PaymentLogFactory.create(invoice=invC, amount=90)
		PaymentLogFactory.create(invoice=invD, amount=360)
		PaymentLogFactory.create(invoice=invD, amount=120)
		PaymentLogFactory.create(invoice=invE, amount=1)

	def test_init(self):
		resp = self.post('api', data={'action': 'init', 'token': EXAMPLE_PASSWORD})
		self.assert20X(resp)  # type: ignore
		out = resp.json()
		self.assertEqual(len(out['_children'][0]['_children']), 1)
		pset = out['_children'][0]['_children'][0]
		self.assertEqual(pset['approved'], False)
		self.assertEqual(pset['clubs'], 120)
		self.assertEqual(pset['hours'], 37)
		self.assertEqual(pset['feedback'], 'Meow')
		self.assertEqual(pset['special_notes'], 'Purr')

		inquiries = out['_children'][1]['inquiries']
		self.assertEqual(len(inquiries), 3)
		self.assertEqual(inquiries[0]['unlock_inquiry_count'], 8)
		self.assertEqual(inquiries[0]['total_inquiry_count'], 10)

	def test_invoice(self):
		data = {
			'action': 'invoice',
			'token': EXAMPLE_PASSWORD,
			'adjustment.alice.aardvark': -240,
			'adjustment.eve.edgeworth': -474,
			'adjustment.l.lawliet': 1337,
			'extras.alice.aardvark': 10,
			'extras.david.darling': 10,
			'extras.mihael.keehl': -9001,
			'total_paid.alice.aardvark': 250,
			'total_paid.bob.beta': 480,
			'total_paid.carol.cutie': 110,
			'total_paid.eve.edgeworth': 5,
			'total_paid.nate.river': 1152
		}
		resp = self.post('api', data=data)
		self.assert20X(resp)  # type: ignore

		# check the response contains exactly missed entries
		out = resp.json()
		self.assertEqual(len(out), 3)
		self.assertTrue('adjustment.l.lawliet' in out)
		self.assertTrue('extras.mihael.keehl' in out)
		self.assertTrue('total_paid.nate.river' in out)

		# check the invoices are correct
		invoice_alice = Invoice.objects.get(student__user__first_name="Alice")
		invoice_bob = Invoice.objects.get(student__user__first_name="Bôb B.")
		invoice_carol = Invoice.objects.get(student__user__first_name="Carol")
		invoice_david = Invoice.objects.get(student__user__first_name="David")
		invoice_eve = Invoice.objects.get(student__user__first_name="Eve")

		self.assertAlmostEqual(invoice_alice.adjustment, -240)
		self.assertAlmostEqual(invoice_alice.extras, 10)
		self.assertAlmostEqual(invoice_alice.total_paid, 250)

		self.assertAlmostEqual(invoice_bob.adjustment, 0)
		self.assertAlmostEqual(invoice_bob.extras, 0)
		self.assertAlmostEqual(invoice_bob.total_paid, 480)

		self.assertAlmostEqual(invoice_carol.adjustment, 0)
		self.assertAlmostEqual(invoice_carol.extras, 0)
		self.assertAlmostEqual(invoice_carol.total_paid, 320)

		self.assertAlmostEqual(invoice_david.adjustment, 0)
		self.assertAlmostEqual(invoice_david.extras, 10)
		self.assertAlmostEqual(invoice_david.total_paid, 480)

		self.assertAlmostEqual(invoice_eve.adjustment, -474)
		self.assertAlmostEqual(invoice_eve.extras, 0)
		self.assertAlmostEqual(invoice_eve.total_paid, 6)

	def test_problem(self):
		resp = self.post('api', data={'action': 'get_hints', 'puid': '18SLA7'})
		self.assert20X(resp)  # type: ignore
		out = resp.json()
		self.assertEqual(len(out['hints']), 0)

		self.assertPost20X(
			'api', data={
				'action': 'add_hints',
				'puid': '18SLA7',
				'content': 'get',
			}
		)
		self.assertPost20X(
			'api', data={
				'action': 'add_hints',
				'puid': '18SLA7',
				'content': 'gud',
			}
		)

		resp = self.post('api', data={'action': 'get_hints', 'puid': '18SLA7'})
		self.assert20X(resp)  # type: ignore
		out = resp.json()
		self.assertEqual(len(out['hints']), 2)
		self.assertTrue(Hint.objects.filter(number=0, content='get').exists())
		self.assertTrue(Hint.objects.filter(number=10, content='gud').exists())
