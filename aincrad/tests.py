from hashlib import sha256

from core.factories import UnitFactory
from dashboard.factories import PSetFactory
from django.test.utils import override_settings
from otisweb.tests import OTISTestCase
from roster.factories import StudentFactory, UnitInquiryFactory

EXAMPLE_PASSWORD = 'take just the first 24'
TARGET_HASH = sha256(EXAMPLE_PASSWORD.encode('ascii')).hexdigest()


@override_settings(API_TARGET_HASH=TARGET_HASH)
class TestVenueQAPI(OTISTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		alice = StudentFactory.create()
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

	def test_init(self):
		resp = self.post('api', data={'action': 'init', 'token': EXAMPLE_PASSWORD})
		self.assert20X(resp)
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
