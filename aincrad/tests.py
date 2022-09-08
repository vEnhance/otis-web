from hashlib import sha256

from arch.models import Hint
from core.factories import SemesterFactory, UnitFactory
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
		active_semester = SemesterFactory.create(name="New")
		old_semester = SemesterFactory.create(name="Old", active=False)

		alice = StudentFactory.create(
			user__first_name="Alice", user__last_name="Aardvárk", semester=active_semester
		)
		bob = StudentFactory.create(
			user__first_name="Bôb B.", user__last_name="Bèta", semester=active_semester
		)
		carol = StudentFactory.create(
			user__first_name="Carol", user__last_name="Cutie", semester=active_semester
		)
		david = StudentFactory.create(
			user__first_name="David", user__last_name="Darling", semester=active_semester
		)
		eve = StudentFactory.create(
			user__first_name="Eve", user__last_name="Edgeworth", semester=active_semester
		)
		old_alice = StudentFactory.create(user=alice.user, semester=old_semester)

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
		PSetFactory.create_batch(2, student=bob, approved=False)
		PSetFactory.create_batch(3, student=carol, approved=False)
		PSetFactory.create_batch(7, student=alice, approved=True)
		PSetFactory.create_batch(2, student=alice, approved=False, rejected=True)
		PSetFactory.create_batch(4, student=alice, approved=False)
		PSetFactory.create_batch(3, approved=True)
		PSetFactory.create_batch(4, student=old_alice, approved=True)
		PSetFactory.create_batch(2, student=old_alice, approved=False)

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
		resp = self.post('api', json={'action': 'init', 'token': EXAMPLE_PASSWORD})
		self.assert20X(resp)  # type: ignore
		out = resp.json()
		self.assertEqual(len(out['_children'][0]['_children']), 10)

		pset_data = out['_children'][0]
		self.assertEqual(pset_data['_name'], 'Problem sets')

		pset0 = pset_data['_children'][0]
		self.assertEqual(pset0['approved'], False)
		self.assertEqual(pset0['clubs'], 120)
		self.assertEqual(pset0['hours'], 37)
		self.assertEqual(pset0['feedback'], 'Meow')
		self.assertEqual(pset0['special_notes'], 'Purr')
		self.assertEqual(pset0['student__user__first_name'], 'Alice')
		self.assertEqual(pset0['num_approved_all'], 11)
		self.assertEqual(pset0['num_approved_current'], 7)

		pset1 = pset_data['_children'][1]
		self.assertEqual(pset1['approved'], False)
		self.assertEqual(pset1['student__user__first_name'], 'Bôb B.')
		self.assertEqual(pset1['num_approved_all'], 0)
		self.assertEqual(pset1['num_approved_current'], 0)

		inquiries = out['_children'][1]['inquiries']
		self.assertEqual(len(inquiries), 3)
		self.assertEqual(inquiries[0]['unlock_inquiry_count'], 8)
		self.assertEqual(inquiries[0]['total_inquiry_count'], 10)

	def test_invoice(self):
		resp = self.post(
			'api',
			json={
				'action': 'invoice',
				'token': EXAMPLE_PASSWORD,
				'entries':
					{
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
						'total_paid.nate.river': 1152,
					}
			}
		)
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
		resp = self.post('api', json={'action': 'get_hints', 'puid': '18SLA7'})
		self.assert20X(resp)  # type: ignore
		out = resp.json()
		self.assertEqual(len(out['hints']), 0)

		self.assertPost20X(
			'api', json={
				'action': 'add_hints',
				'puid': '18SLA7',
				'content': 'get',
			}
		)
		self.assertPost20X(
			'api', json={
				'action': 'add_hints',
				'puid': '18SLA7',
				'content': 'gud',
			}
		)

		resp = self.post('api', json={'action': 'get_hints', 'puid': '18SLA7'})
		self.assert20X(resp)  # type: ignore
		out = resp.json()
		self.assertEqual(len(out['hints']), 2)
		self.assertTrue(Hint.objects.filter(number=0, content='get').exists())
		self.assertTrue(Hint.objects.filter(number=10, content='gud').exists())
