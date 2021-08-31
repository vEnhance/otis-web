from hashlib import sha256

from core.factories import UnitFactory
from dashboard.factories import PSetFactory
from django.test.utils import override_settings
from otisweb.tests import OTISTestCase
from roster.factories import StudentFactory

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
		alice.curriculum.add(submitted_unit)
		alice.curriculum.add(requested_unit)
		alice.unlocked_units.add(submitted_unit)

	def test_init(self):
		resp = self.post('api', data={'action': 'init', 'token': EXAMPLE_PASSWORD})
		self.assert20X(resp)
		out = resp.json()
		self.assertEqual(len(out['_children'][0]['_children']), 1)
		pset = out['_children'][0]['_children'][0]
		assert pset['approved'] is False
		assert pset['clubs'] == 120
		assert pset['hours'] == 37
		assert pset['feedback'] == 'Meow'
		assert pset['special_notes'] == 'Purr'
